import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import { fetchProjects } from "../lib/api";
import { useAsyncValue } from "../hooks/useAsyncValue";

export function DashboardPage() {
  const { data, loading, error } = useAsyncValue(fetchProjects, []);
  const projects = data ?? [];
  const failedCount = projects.filter((item) => item.latest_status === "failed").length;
  const completedCount = projects.filter((item) => item.latest_status === "completed").length;

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <SectionHeader
          eyebrow="控制中心"
          title="不再依赖终端也能管理整个视频流水线"
          body="这个控制台用于管理 AI 视频生成流程，清楚查看节点状态、产物文件和配置，并逐步接入运行控制。"
        />
      </section>

      <section className="metrics-grid">
        <MetricCard label="项目数" value={projects.length} helper="来自 runs/projects" />
        <MetricCard label="已完成" value={completedCount} helper="按最新运行状态统计" />
        <MetricCard label="失败项" value={failedCount} helper="需要人工处理" />
      </section>

      <section className="content-card">
        <SectionHeader
          eyebrow="最近活动"
          title="项目列表"
          body="当前后端已经支持项目发现和配置管理，下一步会接入运行控制。"
        />
        {loading ? <p>正在加载项目...</p> : null}
        {error ? <p className="error-copy">{error}</p> : null}
        {!loading && !error ? (
          <div className="project-list-compact">
            {projects.map((project) => (
              <article key={project.project_id} className="project-card">
                <div className="project-card-title">{project.slug}</div>
                <div className="project-card-meta">{project.latest_status}</div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
