import { apiClient } from './client';
import { mapProjectDto } from './mappers';
import { parseListSafely, projectDtoSchema } from './schemas';
import type {
  CreateProjectResponseDto,
  Project,
  ProjectsResponseDto
} from './types';

interface CreateProjectInput {
  slug: string;
  name: string;
  description?: string;
}

interface UpdateProjectInput {
  name?: string;
  archived?: boolean;
  // undefined: leave the description unchanged; '' clears it.
  description?: string;
}

async function fetchProjects(archived: boolean): Promise<Project[]> {
  const endpoint = archived ? '/projects?archived=true' : '/projects';
  const response = await apiClient<ProjectsResponseDto>(endpoint);
  return parseListSafely(projectDtoSchema, response.projects).map(mapProjectDto);
}

export function getProjects(): Promise<Project[]> {
  return fetchProjects(false);
}

export function getArchivedProjects(): Promise<Project[]> {
  return fetchProjects(true);
}

export async function createProject(data: CreateProjectInput): Promise<Project> {
  const response = await apiClient<CreateProjectResponseDto>('/projects', {
    method: 'POST',
    body: JSON.stringify({
      slug: data.slug,
      name: data.name,
      description: data.description
    })
  });

  return mapProjectDto(projectDtoSchema.parse(response.project));
}

export async function updateProject(
  slug: string,
  data: UpdateProjectInput
): Promise<Project> {
  const response = await apiClient<CreateProjectResponseDto>(`/projects/${slug}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });

  return mapProjectDto(projectDtoSchema.parse(response.project));
}

export async function deleteProject(slug: string): Promise<void> {
  await apiClient<{ status?: string }>(`/projects/${slug}`, {
    method: 'DELETE'
  });
}
