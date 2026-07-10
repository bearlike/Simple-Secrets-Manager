/**
 * Copy-ready snippets for consuming one project/config.
 *
 * The label names, the projection directory and the dotenv file name below are
 * a CONTRACT with the reloader (`ssm_reload/config.py`) and the renderer
 * (`ssm_projection/sink.py::env_filename`). A snippet that drifts from them
 * hands the operator a stack that looks wired up and silently never reloads,
 * so keep the two in step.
 *
 * Pure: takes a project/config pair, returns strings. No React, no I/O.
 */

const ENABLE_LABEL = 'com.bearlike.ssm.enable';
const CONFIG_LABEL = 'com.bearlike.ssm.config';
const REVISION_LABEL = 'com.bearlike.ssm.revision';
const KEYS_LABEL = 'com.bearlike.ssm.keys';
const PROJECTION_DIR = '/run/ssm';
const PROJECTION_VOLUME = 'ssm-env';

export interface Snippet {
  id: string;
  title: string;
  description: string;
  code: string;
}

export interface SnippetGroup {
  id: string;
  label: string;
  snippets: Snippet[];
}

/** Mirrors `ssm_projection.env_filename` — the reloader writes exactly this. */
function envFilePath(projectSlug: string, configSlug: string): string {
  return `${PROJECTION_DIR}/${projectSlug}-${configSlug}.env`;
}

function cliSnippets(projectSlug: string, configSlug: string): Snippet[] {
  const target = `--project ${projectSlug} --config ${configSlug}`;
  return [
    {
      id: 'cli-run',
      title: 'Run a command with these secrets injected',
      description:
        'Secrets live only in the child process environment — nothing is written to disk.',
      code: `ssm run ${target} -- ./your-app`
    },
    {
      id: 'cli-setup',
      title: 'Pin this config to the current directory',
      description:
        'Saves the default so every later `ssm run` here needs no flags.',
      code: `ssm setup ${target}\nssm run -- ./your-app`
    },
    {
      id: 'cli-materialize',
      title: 'Render a dotenv file',
      description:
        "For an env_file:/EnvironmentFile= consumer, or to bootstrap a stack before the reloader's first pass.",
      code: `ssm secrets materialize ${target} --dir ${PROJECTION_DIR}`
    }
  ];
}

function composeSnippets(projectSlug: string, configSlug: string): Snippet[] {
  const envFile = envFilePath(projectSlug, configSlug);
  return [
    {
      id: 'compose-service',
      title: 'Consume this config in a service',
      description:
        'Compose merges env_file with environment, so app-native config stays in git next to the injected secrets.',
      code: `services:
  your-service:
    image: your-image
    env_file:
      - ${envFile}
    environment:
      # App-native config belongs here, not in the secret store.
      TZ: Etc/UTC
    volumes:
      # Read-only: a consumer never writes to the projection volume.
      - ${PROJECTION_VOLUME}:${PROJECTION_DIR}:ro
    labels:
      ${ENABLE_LABEL}: "true"
      ${CONFIG_LABEL}: "${projectSlug}/${configSlug}"

volumes:
  ${PROJECTION_VOLUME}:
    external: true   # created and owned by ssm-reload`
    },
    {
      id: 'compose-reloader',
      title: 'Bootstrap this config on the reloader',
      description:
        "Needed for first boot: compose refuses to start a stack whose env_file does not exist yet, and the reloader otherwise only renders configs a running container is already bound to. Listing it here has the reloader keep the file present before anything consumes it — and re-create it after a reboot, since the projection volume is RAM-backed.",
      code: `services:
  ssm-reload:
    environment:
      SSM_RELOAD_PROJECTION_CONFIGS: "${projectSlug}/${configSlug}"`
    }
  ];
}

function dockerSnippets(projectSlug: string, configSlug: string): Snippet[] {
  return [
    {
      id: 'docker-run',
      title: 'Run a container bound to this config',
      description:
        "docker's --env-file is not a dotenv parser — it keeps quotes literally — so feed it `secrets download`, whose output is unquoted. Process substitution (bash/zsh) keeps the values off disk. The labels are what let the reloader find this container later.",
      code: `docker run -d --name your-service \\
  --env-file <(ssm secrets download --project ${projectSlug} --config ${configSlug} --format env) \\
  --label ${ENABLE_LABEL}=true \\
  --label ${CONFIG_LABEL}=${projectSlug}/${configSlug} \\
  your-image`
    },
    {
      id: 'docker-inspect',
      title: 'Check what the reloader has applied',
      description:
        'The reloader stamps the config revision it injected, and the key names it owns, onto the container.',
      code: `docker inspect your-service \\
  --format '{{index .Config.Labels "${REVISION_LABEL}"}} {{index .Config.Labels "${KEYS_LABEL}"}}'`
    }
  ];
}

export function buildConfigSnippets(
  projectSlug: string,
  configSlug: string
): SnippetGroup[] {
  return [
    { id: 'cli', label: 'CLI', snippets: cliSnippets(projectSlug, configSlug) },
    {
      id: 'compose',
      label: 'Docker Compose',
      snippets: composeSnippets(projectSlug, configSlug)
    },
    {
      id: 'docker',
      label: 'docker run',
      snippets: dockerSnippets(projectSlug, configSlug)
    }
  ];
}
