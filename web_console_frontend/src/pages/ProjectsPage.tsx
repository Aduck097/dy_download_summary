import { Link } from "react-router-dom";

import { SectionHeader } from "../components/SectionHeader";
import { StatusPill } from "../components/StatusPill";
import { useAsyncValue } from "../hooks/useAsyncValue";
import { fetchProjects } from "../lib/api";
import { formatDateTime } from "../lib/format";

export function ProjectsPage() {
  const { data, loading, error } = useAsyncValue(fetchProjects, []);
  const projects = data ?? [];

  return (
    <div className="page-stack">
      <section className="content-card">
        <SectionHeader
          eyebrow="项目"
          title="全部运行项目"
          body="每张卡片代表一个项目 slug 下最新发现的一次运行。"
        />
        {loading ? <p>正在加载项目...</p> : null}
        {error ? <p className="error-copy">{error}</p> : null}
        {!loading && !error ? (
          <div className="project-grid">
            {projects.map((project) => (
              <Link key={project.project_id} to={`/projects/${project.project_id}`} className="project-card project-card-link">
                <div className="project-card-top">
                  <div>
                    <div className="project-card-title">{project.slug}</div>
                    <div className="project-card-subtitle">{project.latest_run_key}</div>
                  </div>
                  <StatusPill status={project.latest_status} />
                </div>
                <div className="project-card-source">{project.source_url ?? "暂无源链接"}</div>
                <div className="project-card-meta">{formatDateTime(project.updated_at)}</div>
              </Link>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
