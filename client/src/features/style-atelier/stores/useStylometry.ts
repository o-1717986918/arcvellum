import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { stylometryClient as client } from "../services/stylometryClient";
import type { CorpusSource, CreatorControls, MetricRow, StyloCompiled, StyloJob,
  StyloMeasurement, StyloProfile, StyloVersion, StyloWorkbench } from "../stylometryTypes";

export function useStylometry(root: Ref<string>) {
  const workbench = ref<StyloWorkbench | null>(null), profile = ref<StyloProfile | null>(null);
  const metrics = ref<MetricRow[]>([]), controls = ref<CreatorControls | null>(null);
  const sources = ref<CorpusSource[]>([]), title = ref("我的语料"), intent = ref("");
  const dependency = ref(""), candidateTree = ref(""), fragment = ref("");
  const compiled = ref<StyloCompiled | null>(null), selectedVersion = ref<StyloVersion | null>(null);
  const report = ref<StyloMeasurement | null>(null), text = ref("");
  const busy = ref(false), error = ref(""), notice = ref(""), job = ref<StyloJob | null>(null);
  const jobs = ref<StyloJob[]>([]), tab = ref("corpus");
  const combine = ref<"append" | "replace">("append"), usage = ref<"guide" | "observe">("guide");
  let generation = 0, timer: ReturnType<typeof setTimeout> | undefined;
  const running = computed(() => ["queued", "running", "cancelling"].includes(job.value?.status || ""));
  const dirty = computed(() => Boolean(selectedVersion.value && (
    fragment.value !== selectedVersion.value.fragment_text || intent.value !== selectedVersion.value.intent ||
    dependency.value !== selectedVersion.value.dependency_json ||
    JSON.stringify(controls.value) !== JSON.stringify(JSON.parse(selectedVersion.value.controls_json)))));
  const combined = computed(() => [workbench.value?.style_context.author_directive,
    usage.value === "guide" && combine.value === "replace" ? "" : workbench.value?.style_context.formal,
    usage.value === "guide" ? fragment.value : ""].filter(Boolean).join("\n\n"));

  async function run<T>(request: (project: string) => Promise<T>, apply: (result: T) => void): Promise<void> {
    const epoch = generation, project = root.value;
    if (!project) { error.value = "请先选择作品。"; return; }
    busy.value = true; error.value = ""; notice.value = "";
    try {
      const result = await request(project);
      if (epoch === generation) apply(result);
    } catch (problem) {
      if (epoch === generation) error.value = problem instanceof Error ? problem.message : String(problem);
    } finally { if (epoch === generation) busy.value = false; }
  }
  function load(): Promise<void> {
    return run(async project => ({ workbench: await client.workbench(project), jobs: await client.jobs(project) }), result => {
      workbench.value = result.workbench; jobs.value = result.jobs.jobs;
      combine.value = result.workbench.mount.combine; usage.value = result.workbench.mount.usage;
      const active = jobs.value.find(item => ["queued", "running", "cancelling", "interrupted"].includes(item.status));
      if (active) { job.value = active; schedule(); }
    });
  }
  function selectProfile(id: string): Promise<void> {
    return run(async project => ({ profile: await client.profile(project, id), parameters: await client.parameters(project, id) }), result => {
      profile.value = result.profile; metrics.value = result.parameters.metrics; controls.value = result.parameters.controls;
      title.value = result.profile.title; dependency.value = ""; fragment.value = "";
      selectedVersion.value = null; compiled.value = null; report.value = null; tab.value = "parameters";
    });
  }
  function selectVersion(id: string): Promise<void> {
    return run(async project => {
      const version = await client.version(project, id);
      return { version, profile: await client.profile(project, version.profile_id),
        parameters: await client.parameters(project, version.profile_id, version.dependency_json) };
    }, result => {
      selectedVersion.value = result.version; profile.value = result.profile; metrics.value = result.parameters.metrics;
      controls.value = JSON.parse(result.version.controls_json); dependency.value = result.version.dependency_json;
      title.value = result.version.title; intent.value = result.version.intent; fragment.value = result.version.fragment_text;
      compiled.value = JSON.parse(result.version.compiled_json); report.value = null; tab.value = "mount";
    });
  }
  function request(project: string) {
    if (!profile.value || !controls.value) throw new Error("先选择语料画像。单篇统计可在左侧直接运行。");
    return { project_root: project, profile_id: profile.value.profile_id, controls_json: JSON.stringify(controls.value),
      title: title.value, intent: intent.value, dependency_json: dependency.value };
  }
  function compile(): Promise<void> {
    return run(project => client.compile(request(project)), result => {
      compiled.value = result; fragment.value = result.fragment_text; notice.value = "已重新编译，可直接修改片段后保存。";
    });
  }
  function save(): Promise<void> {
    return run(async project => ({ version: await client.save({ ...request(project), fragment_override: fragment.value || null }),
      workbench: await client.workbench(project) }), result => {
      selectedVersion.value = result.version; workbench.value = result.workbench; fragment.value = result.version.fragment_text;
      compiled.value = JSON.parse(result.version.compiled_json); report.value = null;
      notice.value = "已保存新版本。选择使用方式并挂载到后续场景。";
    });
  }
  function mount(enabled: boolean): Promise<void> {
    return run(async project => {
      if (enabled && (!selectedVersion.value || dirty.value)) throw new Error("请先保存当前修改，再挂载该版本。");
      await client.mount(project, selectedVersion.value?.version_id || "", enabled, workbench.value?.mount.revision || 0, combine.value, usage.value);
      return client.workbench(project);
    }, result => { workbench.value = result; notice.value = enabled ? "已挂载，后续新场景生效。" : "已卸载，后续新场景生效。"; });
  }
  function measure(): Promise<void> {
    const body = text.value, tree = candidateTree.value, version = selectedVersion.value?.version_id;
    const profileId = profile.value?.profile_id;
    report.value = null;
    return run(project => client.measure(project, body, version, tree), result => {
      if (body !== text.value || tree !== candidateTree.value || version !== selectedVersion.value?.version_id ||
        profileId !== profile.value?.profile_id) return;
      report.value = result; notice.value = "测量完成；短文本或未提供树的指标显示缺测。";
    });
  }
  function launch(): Promise<void> {
    return run(project => client.launch(project, title.value, sources.value), result => {
      job.value = result; schedule(); notice.value = "统计已在后台开始，离开本页后仍会继续。";
    });
  }
  function jobAction(action: "cancel" | "resume"): Promise<void> {
    return run(project => client.jobAction(project, job.value!.job_id, action), result => { job.value = result; schedule(); });
  }
  function schedule(): void { clearTimeout(timer); if (running.value) timer = setTimeout(() => void poll(), 1000); }
  async function poll(): Promise<void> {
    const epoch = generation, project = root.value, id = job.value?.job_id;
    if (!id) return;
    try {
      const result = await client.job(project, id);
      if (epoch !== generation) return;
      job.value = result;
      if (result.status === "completed" && result.result) {
        if ("profile_id" in result.result) { await load(); await selectProfile(result.result.profile_id); }
        else { report.value = result.result.result; notice.value = "单篇统计完成。建立可挂载画像需训练和留出语料。"; }
      }
    } catch (problem) { if (epoch === generation) error.value = String(problem); }
    finally { if (epoch === generation) schedule(); }
  }
  function loadDependency(): Promise<void> {
    return run(project => client.parameters(project, profile.value!.profile_id, dependency.value), result => {
      metrics.value = result.metrics;
      const old = controls.value?.targets || [];
      controls.value = { ...result.controls, targets: result.controls.targets.map(row => old.find(item => item.id === row.id) || row) };
      notice.value = "参考树已核验；七项依存参数已加入。";
    });
  }
  function restore(): void { if (controls.value) controls.value.targets = metrics.value.map(row => ({ id: row.id,
    unit: row.unit, ...row.suggested, enabled: row.group === "primary" && row.available })); }
  async function selectJob(row: StyloJob): Promise<void> {
    job.value = row; schedule();
    if (row.status === "completed" && row.result) {
      if ("profile_id" in row.result) await selectProfile(row.result.profile_id);
      else report.value = row.result.result;
    }
  }
  watch([text, candidateTree], () => { report.value = null; }, { flush: "sync" });
  watch(root, () => {
    generation++; clearTimeout(timer); workbench.value = null; profile.value = null; selectedVersion.value = null;
    sources.value = []; metrics.value = []; controls.value = null; dependency.value = ""; candidateTree.value = "";
    fragment.value = ""; text.value = ""; report.value = null; compiled.value = null; intent.value = "";
    title.value = "我的语料"; tab.value = "corpus"; job.value = null; jobs.value = []; error.value = ""; notice.value = ""; busy.value = false;
    if (root.value) void load();
  }, { immediate: true });
  onBeforeUnmount(() => { generation++; clearTimeout(timer); });
  return { workbench, profile, metrics, controls, sources, title, intent, dependency, candidateTree, fragment,
    compiled, selectedVersion, report, text, busy, error, notice, job, jobs, tab, combine, usage, running, dirty, combined,
    load, selectProfile, selectVersion, compile, save, mount, measure, launch, jobAction, loadDependency, restore, selectJob };
}
