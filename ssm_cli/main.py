from __future__ import annotations

import json
import os
import stat
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import click
from rich.console import Console
from rich.table import Table

from ssm_cli import auth
from ssm_cli.api import ApiClient, ApiError, normalize_base_url
from ssm_cli.cache import load_secret_cache, save_secret_cache
from ssm_cli.config import (
    DEFAULT_PROFILE,
    GlobalConfig,
    LocalConfig,
    ProfileConfig,
    load_global_config,
    save_global_config,
    save_local_config,
)
from ssm_cli.exceptions import CliError
from ssm_cli.resolve import Resolution, resolve_context
from ssm_cli.run_utils import render_env_lines, run_with_env

console = Console()
err_console = Console(stderr=True)


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"[red]Error:[/red] {message}")
    raise click.exceptions.Exit(code)


def _handle_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except CliError as exc:
            _fail(exc.message, exc.exit_code)
        except ApiError as exc:
            _fail(f"{exc.message} (status={exc.status_code})", 1)

    return wrapper


def _profile_name(override: str | None, cfg: GlobalConfig) -> str:
    env = os.getenv("SSM_PROFILE")
    return (override or env or cfg.active_profile or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE


def _ensure_profile(cfg: GlobalConfig, profile_name: str) -> ProfileConfig:
    profile = cfg.profiles.get(profile_name)
    if profile is None:
        profile = ProfileConfig()
        cfg.profiles[profile_name] = profile
    return profile


def _fetch_secrets(
    resolution: Resolution,
    *,
    offline: bool,
    cache_ttl: int,
) -> tuple[dict[str, str], str]:
    if not resolution.base_url or not resolution.project or not resolution.config:
        raise CliError("Missing base_url/project/config for secret retrieval", exit_code=2)

    if offline:
        cached = load_secret_cache(
            resolution.base_url,
            resolution.project,
            resolution.config,
            max_age_seconds=cache_ttl,
        )
        if cached is None:
            raise CliError("No cached secrets found for offline mode", exit_code=4)
        return cached, "cache"

    client = ApiClient(resolution.base_url, token=resolution.token)
    try:
        data = client.export_secrets_json(resolution.project, resolution.config)
        save_secret_cache(resolution.base_url, resolution.project, resolution.config, data)
        return data, "remote"
    except ApiError:
        cached = load_secret_cache(
            resolution.base_url,
            resolution.project,
            resolution.config,
            max_age_seconds=cache_ttl,
        )
        if cached is not None:
            console.print("[yellow]Using cached secrets because live fetch failed.[/yellow]")
            return cached, "cache-fallback"
        raise


def _print_env_table(secrets: dict[str, str], show_values: bool) -> None:
    table = Table(title="Resolved environment", show_lines=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")
    for key in sorted(secrets.keys()):
        value = secrets[key] if show_values else "[redacted]"
        table.add_row(key, value)
    console.print(table)


@click.group(help="Simple Secrets Manager CLI")
def cli() -> None:
    pass


@cli.command(help="Configure API base URL for a profile")
@click.option("--base-url", required=True, help="Base URL (for example http://localhost:8080/api)")
@click.option("--profile", default=None, help="Profile name")
@click.option("--activate/--no-activate", default=True, help="Set profile as active")
@_handle_errors
def configure(base_url: str, profile: str | None, activate: bool) -> None:
    cfg = load_global_config()
    profile_name = _profile_name(profile, cfg)
    normalized = normalize_base_url(base_url)
    profile_cfg = _ensure_profile(cfg, profile_name)
    profile_cfg.base_url = normalized
    cfg.base_url = normalized
    if activate:
        cfg.active_profile = profile_name
    save_global_config(cfg)
    console.print(f"Configured [bold]{profile_name}[/bold] -> {normalized}")


@cli.group(name="auth", help="Authentication helpers")
def auth_cmd() -> None:
    pass


@auth_cmd.command("set-token", help="Store a token for the current base URL/profile")
@click.option("--token", prompt=True, hide_input=True, help="Token value")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--profile", default=None, help="Profile name")
@_handle_errors
def auth_set_token(token: str, base_url: str | None, profile: str | None) -> None:
    resolution = resolve_context(base_url=base_url, profile=profile, require_base_url=True)
    storage = auth.set_token(resolution.profile, resolution.base_url or "", token.strip())
    console.print(f"Token saved for profile [bold]{resolution.profile}[/bold] ({storage})")


@cli.command(help="Login with username/password and store returned token")
@click.option("--username", prompt=True, help="Username")
@click.option("--password", prompt=True, hide_input=True, help="Password")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--profile", default=None, help="Profile name")
@_handle_errors
def login(username: str, password: str, base_url: str | None, profile: str | None) -> None:
    resolution = resolve_context(base_url=base_url, profile=profile, require_base_url=True)
    client = ApiClient(resolution.base_url or "")
    token_payload = client.login_userpass(username.strip(), password)
    token = token_payload.get("token")
    if not isinstance(token, str):
        raise CliError("Login response did not include a token")

    storage = auth.set_token(resolution.profile, resolution.base_url or "", token)

    cfg = load_global_config()
    profile_cfg = _ensure_profile(cfg, resolution.profile)
    if not profile_cfg.base_url:
        profile_cfg.base_url = resolution.base_url
    if cfg.active_profile != resolution.profile:
        cfg.active_profile = resolution.profile
    save_global_config(cfg)

    expires = token_payload.get("expires_at")
    if isinstance(expires, str) and expires:
        console.print(f"Logged in. Token stored in {storage}. Expires at {expires}")
    else:
        console.print(f"Logged in. Token stored in {storage}.")


@cli.command(help="Remove locally stored token")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--profile", default=None, help="Profile name")
@click.option("--all-profiles", is_flag=True, default=False, help="Remove all file-backed tokens")
@_handle_errors
def logout(base_url: str | None, profile: str | None, all_profiles: bool) -> None:
    if all_profiles:
        auth.clear_all_tokens()
        console.print("Cleared all locally stored tokens.")
        return

    resolution = resolve_context(base_url=base_url, profile=profile, require_base_url=True)
    auth.clear_token(resolution.profile, resolution.base_url or "")
    console.print(f"Cleared token for profile [bold]{resolution.profile}[/bold].")


@cli.command(help="Set project/config defaults for current directory")
@click.option("--project", prompt=True, help="Project slug")
@click.option("--config", "config_name", prompt=True, help="Config slug")
@click.option("--profile", default=None, help="Profile name")
@click.option("--sync-profile/--local-only", default=True, help="Also save as profile defaults")
@_handle_errors
def setup(project: str, config_name: str, profile: str | None, sync_profile: bool) -> None:
    resolution = resolve_context(profile=profile)
    save_local_config(LocalConfig(profile=resolution.profile, project=project.strip(), config=config_name.strip()))

    if sync_profile:
        cfg = load_global_config()
        profile_cfg = _ensure_profile(cfg, resolution.profile)
        profile_cfg.project = project.strip()
        profile_cfg.config = config_name.strip()
        if resolution.base_url and not profile_cfg.base_url:
            profile_cfg.base_url = resolution.base_url
        save_global_config(cfg)

    console.print("Directory defaults saved in .ssm/config.json")


@cli.command(
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
    help="Run command with secrets injected into child process environment",
)
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--project", default=None, help="Project slug override")
@click.option("--config", "config_name", default=None, help="Config slug override")
@click.option("--profile", default=None, help="Profile name")
@click.option("--offline", is_flag=True, default=False, help="Use cached secrets only")
@click.option("--cache-ttl", default=3600, show_default=True, type=int, help="Cache max age in seconds")
@click.option("--print-env", is_flag=True, default=False, help="Print resolved keys before execution")
@click.option("--show-values", is_flag=True, default=False, help="Show values with --print-env")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@_handle_errors
def run(
    base_url: str | None,
    project: str | None,
    config_name: str | None,
    profile: str | None,
    offline: bool,
    cache_ttl: int,
    print_env: bool,
    show_values: bool,
    command: tuple[str, ...],
) -> None:
    if not command:
        raise CliError("Command is required after `ssm run --`", exit_code=2)
    resolution = resolve_context(
        base_url=base_url,
        project=project,
        config=config_name,
        profile=profile,
        require_base_url=True,
        require_project_config=True,
        require_token=True,
    )
    secrets, source = _fetch_secrets(resolution, offline=offline, cache_ttl=cache_ttl)

    if print_env:
        _print_env_table(secrets, show_values=show_values)

    if source != "remote":
        console.print(f"Using secrets from [bold]{source}[/bold].")

    code = run_with_env(command, secrets)
    raise click.exceptions.Exit(code)


@cli.group(help="Secret export and mount commands")
def secrets() -> None:
    pass


@secrets.command("download", help="Download secrets to stdout")
@click.option("--format", "output_format", type=click.Choice(["json", "env"]), default="json", show_default=True)
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--project", default=None, help="Project slug override")
@click.option("--config", "config_name", default=None, help="Config slug override")
@click.option("--profile", default=None, help="Profile name")
@click.option("--offline", is_flag=True, default=False, help="Use cached secrets only")
@click.option("--cache-ttl", default=3600, show_default=True, type=int, help="Cache max age in seconds")
@_handle_errors
def secrets_download(
    output_format: str,
    base_url: str | None,
    project: str | None,
    config_name: str | None,
    profile: str | None,
    offline: bool,
    cache_ttl: int,
) -> None:
    resolution = resolve_context(
        base_url=base_url,
        project=project,
        config=config_name,
        profile=profile,
        require_base_url=True,
        require_project_config=True,
        require_token=True,
    )
    secrets_data, source = _fetch_secrets(resolution, offline=offline, cache_ttl=cache_ttl)
    if source != "remote":
        console.print(f"Using secrets from [bold]{source}[/bold].", style="yellow")

    if output_format == "json":
        console.print_json(json.dumps(secrets_data, sort_keys=True))
        return

    console.print(render_env_lines(secrets_data), soft_wrap=True)


@secrets.command("mount", help="Write secrets to a named pipe (FIFO)")
@click.option("--path", "fifo_path", required=True, type=click.Path(path_type=Path), help="FIFO path")
@click.option("--format", "output_format", type=click.Choice(["json", "env"]), default="env", show_default=True)
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--project", default=None, help="Project slug override")
@click.option("--config", "config_name", default=None, help="Config slug override")
@click.option("--profile", default=None, help="Profile name")
@click.option("--offline", is_flag=True, default=False, help="Use cached secrets only")
@click.option("--cache-ttl", default=3600, show_default=True, type=int, help="Cache max age in seconds")
@click.option("--keep", is_flag=True, default=False, help="Keep FIFO after write")
@_handle_errors
def secrets_mount(
    fifo_path: Path,
    output_format: str,
    base_url: str | None,
    project: str | None,
    config_name: str | None,
    profile: str | None,
    offline: bool,
    cache_ttl: int,
    keep: bool,
) -> None:
    resolution = resolve_context(
        base_url=base_url,
        project=project,
        config=config_name,
        profile=profile,
        require_base_url=True,
        require_project_config=True,
        require_token=True,
    )
    secrets_data, source = _fetch_secrets(resolution, offline=offline, cache_ttl=cache_ttl)

    payload = json.dumps(secrets_data, sort_keys=True) if output_format == "json" else render_env_lines(secrets_data)

    if fifo_path.exists():
        file_mode = fifo_path.stat().st_mode
        if not stat.S_ISFIFO(file_mode):
            raise CliError(f"Path exists and is not a FIFO: {fifo_path}")
        fifo_path.unlink()

    fifo_path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(fifo_path, mode=0o600)

    console.print(f"FIFO created at {fifo_path}. Waiting for reader...")
    if source != "remote":
        console.print(f"Using secrets from [bold]{source}[/bold].", style="yellow")

    try:
        with fifo_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        console.print("Payload written to FIFO.")
    finally:
        if not keep and fifo_path.exists():
            fifo_path.unlink()


@cli.command(help="Validate the active token and print context")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--profile", default=None, help="Profile name")
@_handle_errors
def whoami(base_url: str | None, profile: str | None) -> None:
    resolution = resolve_context(
        base_url=base_url,
        profile=profile,
        require_base_url=True,
        require_token=True,
    )

    client = ApiClient(resolution.base_url or "", token=resolution.token)
    scope_message = ""
    try:
        projects = client.list_projects()
        scope_message = f"projects:read available ({len(projects)} visible)"
    except ApiError as exc:
        if exc.status_code == 403:
            scope_message = "token valid, but missing projects:read"
        else:
            raise

    token_preview = "[hidden]"
    if resolution.token and len(resolution.token) >= 8:
        token_preview = f"{resolution.token[:4]}...{resolution.token[-4:]}"

    table = Table(title="Current session")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Profile", resolution.profile)
    table.add_row("Base URL", resolution.base_url or "")
    table.add_row("Token Source", resolution.token_source or "unknown")
    table.add_row("Token", token_preview)
    table.add_row("Scopes", scope_message)
    console.print(table)


@cli.group(help="Manage CLI profiles")
def profile() -> None:
    pass


@profile.command("list", help="List profiles")
@_handle_errors
def profile_list() -> None:
    cfg = load_global_config()
    table = Table(title="Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("Active")
    table.add_column("Base URL")
    table.add_column("Project")
    table.add_column("Config")

    names = sorted(cfg.profiles.keys())
    if not names:
        names = [cfg.active_profile]

    for name in names:
        profile_cfg = cfg.profiles.get(name) or ProfileConfig()
        table.add_row(
            name,
            "yes" if name == cfg.active_profile else "",
            profile_cfg.base_url or "",
            profile_cfg.project or "",
            profile_cfg.config or "",
        )
    console.print(table)


@profile.command("use", help="Set active profile")
@click.argument("name")
@_handle_errors
def profile_use(name: str) -> None:
    profile_name = name.strip()
    if not profile_name:
        raise CliError("Profile name cannot be empty", exit_code=2)

    cfg = load_global_config()
    _ensure_profile(cfg, profile_name)
    cfg.active_profile = profile_name
    save_global_config(cfg)
    console.print(f"Active profile set to [bold]{profile_name}[/bold]")


@profile.command("set", help="Set profile fields")
@click.argument("name")
@click.option("--base-url", default=None, help="Base URL")
@click.option("--project", default=None, help="Default project")
@click.option("--config", "config_name", default=None, help="Default config")
@click.option("--activate", is_flag=True, default=False, help="Set as active profile")
@_handle_errors
def profile_set(name: str, base_url: str | None, project: str | None, config_name: str | None, activate: bool) -> None:
    if not any([base_url, project, config_name, activate]):
        raise CliError("No changes requested. Provide at least one option.", exit_code=2)

    profile_name = name.strip()
    if not profile_name:
        raise CliError("Profile name cannot be empty", exit_code=2)

    cfg = load_global_config()
    profile_cfg = _ensure_profile(cfg, profile_name)

    if base_url:
        normalized = normalize_base_url(base_url)
        profile_cfg.base_url = normalized
        cfg.base_url = normalized
    if project:
        profile_cfg.project = project.strip()
    if config_name:
        profile_cfg.config = config_name.strip()
    if activate:
        cfg.active_profile = profile_name

    save_global_config(cfg)
    console.print(f"Profile [bold]{profile_name}[/bold] updated.")


if __name__ == "__main__":
    cli()
