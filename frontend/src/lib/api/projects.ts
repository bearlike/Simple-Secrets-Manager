import { apiClient } from './client';
import { mapProjectDto } from './mappers';
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

export async function getProjects(): Promise<Project[]> {
  const response = await apiClient<ProjectsResponseDto>('/projects');
  return (response.projects ?? []).map(mapProjectDto);
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

  return mapProjectDto(response.project);
}
