import { useEffect, useMemo, useState } from "react";

import { SectionHeader } from "../components/SectionHeader";
import { fetchConfig, saveConfig, validateConfig } from "../lib/api";

type ValidationState = {
  valid: boolean;
  errors: string[];
} | null;

export function ConfigPage() {
  const [editorValue, setEditorValue] = useState("");
  const [originalValue, setOriginalValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationState>(null);

  useEffect(() => {
    let mounted = true;

    async function loadConfig() {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchConfig();
        if (!mounted) {
          return;
        }

        const pretty = JSON.stringify(data ?? {}, null, 2);
        setEditorValue(pretty);
        setOriginalValue(pretty);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "配置加载失败");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadConfig();

    return () => {
      mounted = false;
    };
  }, []);

  const isDirty = useMemo(() => editorValue !== originalValue, [editorValue, originalValue]);

  function parseEditorValue(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(editorValue) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("配置根节点必须是 JSON 对象");
      }
      return parsed as Record<string, unknown>;
    } catch (parseError) {
      setError(parseError instanceof Error ? parseError.message : "JSON 解析失败");
      return null;
    }
  }

  async function handleValidate() {
    setSuccessMessage(null);
    setError(null);

    const parsed = parseEditorValue();
    if (!parsed) {
      return;
    }

    setValidating(true);
    try {
      const result = await validateConfig(parsed);
      setValidation(result);
      if (result.valid) {
        setSuccessMessage("配置校验通过");
      }
    } catch (validateError) {
      setError(validateError instanceof Error ? validateError.message : "配置校验失败");
    } finally {
      setValidating(false);
    }
  }

  async function handleSave() {
    setSuccessMessage(null);
    setError(null);

    const parsed = parseEditorValue();
    if (!parsed) {
      return;
    }

    setSaving(true);
    try {
      const result = await validateConfig(parsed);
      setValidation(result);
      if (!result.valid) {
        setError("配置校验未通过，已阻止保存");
        return;
      }

      await saveConfig(parsed);
      const pretty = JSON.stringify(parsed, null, 2);
      setEditorValue(pretty);
      setOriginalValue(pretty);
      setSuccessMessage("配置已保存到 config.json");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "配置保存失败");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    setEditorValue(originalValue);
    setValidation(null);
    setError(null);
    setSuccessMessage(null);
  }

  return (
    <div className="page-stack">
      <section className="content-card">
        <SectionHeader
          eyebrow="配置中心"
          title="编辑流程配置"
          body="直接在网页里维护 config.json。保存前会先校验 JSON 结构和必要字段，避免把坏配置写进项目。"
        />
        <div className="config-toolbar">
          <div className="config-toolbar-meta">
            <span className={`status-pill ${isDirty ? "status-running" : "status-completed"}`}>
              {isDirty ? "未保存" : "已同步"}
            </span>
            <span className="config-toolbar-copy">当前编辑的是项目根目录下的 `config.json`</span>
          </div>
          <div className="config-toolbar-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={handleReset}
              disabled={!isDirty || loading || saving || validating}
            >
              重置
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void handleValidate()}
              disabled={loading || saving || validating}
            >
              {validating ? "校验中..." : "校验配置"}
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => void handleSave()}
              disabled={loading || saving}
            >
              {saving ? "保存中..." : "保存配置"}
            </button>
          </div>
        </div>

        {loading ? <p>正在加载配置...</p> : null}
        {error ? <p className="error-copy">{error}</p> : null}
        {successMessage ? <p className="success-copy">{successMessage}</p> : null}

        {validation ? (
          <div className={`validation-panel ${validation.valid ? "is-valid" : "is-invalid"}`}>
            <div className="validation-title">{validation.valid ? "校验通过" : "校验未通过"}</div>
            {validation.errors.length ? (
              <ul className="validation-list">
                {validation.errors.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="validation-copy">当前配置结构正常。</p>
            )}
          </div>
        ) : null}

        {!loading ? (
          <label className="config-editor-block">
            <span className="config-editor-label">配置 JSON</span>
            <textarea
              className="config-editor"
              value={editorValue}
              onChange={(event) => setEditorValue(event.target.value)}
              spellCheck={false}
            />
          </label>
        ) : null}
      </section>
    </div>
  );
}
