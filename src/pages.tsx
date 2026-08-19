// KeySwitch 页面组件（总览 / Key配置 / Provider / Key池 / 应用 / 设置）

import { useEffect, useMemo, useState } from "react";
import {
  api,
  Config,
  KeyStatus,
  UsageInfo,
} from "./lib/api";

// ---------------- 通用小组件 ----------------

export function StatusDot({ u }: { u: UsageInfo | null }) {
  const color = !u || u.status === "error" || u.status === "disabled" ? "#dc2626" : "#16a34a";
  return <span className="dot" style={{ background: color }} />;
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">{title}</div>
        {children}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Btn({
  children,
  onClick,
  primary,
  danger,
  disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  primary?: boolean;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      className={`btn${primary ? " primary" : ""}${danger ? " danger" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function msgOk(msg: string) {
  alert(`✅ ${msg}`);
}
function msgErr(e: unknown) {
  alert(`❌ ${e}`);
}

// ---------------- 总览 ----------------

export function OverviewPage() {
  const [status, setStatus] = useState<KeyStatus[]>([]);
  const [actual, setActual] = useState<Record<string, Record<string, string>>>({});
  const [cfg, setCfg] = useState<Config | null>(null);
  const [busy, setBusy] = useState(false);

  const loadStatus = async (force = false) => {
    try {
      setStatus(await api.getStatus(force));
    } catch (e) {
      msgErr(e);
    }
  };
  const load = async () => {
    // 本地数据（配置 + 各软件实际状态）先渲染，页面不用等用量
    try {
      const [ac, c] = await Promise.all([api.getActualKeys(), api.getConfig()]);
      setActual(ac);
      setCfg(c);
    } catch (e) {
      msgErr(e);
    }
    // 用量信息后台异步填充，不阻塞页面渲染（命中 5 分钟缓存时立即返回）
    loadStatus(false);
  };
  // 手动刷新用量：强制绕过缓存重新查询
  const refreshStatus = () => loadStatus(true);
  useEffect(() => {
    load();
  }, []);

  const saveAuto = async () => {
    if (!cfg) return;
    try {
      await api.saveAutoSettings(cfg.auto_switch.enabled, cfg.auto_switch.trigger_percent, cfg.auto_switch.interval_min);
      msgOk(`智能切换已${cfg.auto_switch.enabled ? "启用" : "停用"}（阈值 ${cfg.auto_switch.trigger_percent}% / ${cfg.auto_switch.interval_min} 分钟）`);
    } catch (e) {
      msgErr(e);
    }
  };

  const smartNow = async () => {
    setBusy(true);
    try {
      const r = await api.smartCheck();
      // 用量明细（让用户确认检测确实在跑）
      const status = await api.getStatus().catch(() => []);
      const usageLines = status
        .map((s) => {
          const u = s.usage;
          if (!u) return `  ${s.provider}/${s.id}: 未配置`;
          if (u.kind === "balance")
            return `  ${s.provider}/${s.id}: 余额 ${u.balance != null ? u.balance.toFixed(2) : "?"}`;
          const pct = [u.percent, u.weekly, u.monthly].filter((v) => v != null).join("/");
          return `  ${s.provider}/${s.id}: 滚动/周/月 = ${pct || "?"}%`;
        })
        .join("\n");
      if (r.switches.length) {
        alert(
          `🔄 智能切换完成：\n` +
            r.switches
              .map((s) => `  ${s.provider}: ${s.from} → ${s.to}（软件: ${s.targets.join("、") || "无"}）`)
              .join("\n") +
            `\n\n⚠️ 相关软件需重启后使用新 key 生效` +
            (usageLines ? `\n\n当前用量：\n${usageLines}` : ``),
        );
      } else if (r.exhausted.length) {
        alert(`⚠️ 告急但无可用 key: ${r.exhausted.join("、")}\n\n当前用量：\n${usageLines}`);
      } else {
        alert(`✅ 检测完成：${r.checked} 个在用 key 全部正常（未达阈值 ${cfg?.auto_switch?.trigger_percent ?? 100}%，无需切换）\n\n当前用量：\n${usageLines}`);
      }
      await load();
    } catch (e) {
      msgErr(e);
    } finally {
      setBusy(false);
    }
  };

  // 用量按 provider:id 索引，用于把后台返回的用量填充进已渲染的 Key 卡片
  const statusMap = useMemo(() => {
    const m: Record<string, KeyStatus> = {};
    for (const s of status) m[`${s.provider}::${s.id}`] = s;
    return m;
  }, [status]);

  return (
    <div className="page">
      <h2 className="page-title">总览</h2>
      <p className="page-sub">各 API Key 的用量 / 余额实时状态</p>

      <div className="cards">
        {cfg
          ? Object.entries(cfg.providers).flatMap(([p, pc]) =>
              pc.keys.map((k) => {
                const s = statusMap[`${p}::${k.id}`];
                return (
                  <div className="card" key={`${p}::${k.id}`}>
                    <div className="card-title">
                      {p} / {k.id}
                    </div>
                    {s?.usage ? (
                      <>
                        <div className="card-big">{s.usage.detail}</div>
                        <div className="card-sub">
                          <StatusDot u={s.usage} /> 状态: {s.usage.status} · {k.note}
                        </div>
                      </>
                    ) : (
                      <div className="card-sub">用量加载中… · {k.note}</div>
                    )}
                  </div>
                );
              }),
            )
          : (
            <div className="card-sub">加载中…</div>
          )}
      </div>

      <div className="row">
        <Btn primary onClick={refreshStatus}>🔄 刷新用量</Btn>
      </div>

      {/* 智能切换卡片 */}
      <div className="auto-card">
        <div className="auto-title">⚡ 智能切换（用量耗尽自动换可用 key，按优先级）</div>
        {cfg && (
          <>
            <label className="row check">
              <input
                type="checkbox"
                checked={cfg.auto_switch.enabled}
                onChange={(e) =>
                  setCfg({ ...cfg, auto_switch: { ...cfg.auto_switch, enabled: e.target.checked } })
                }
              />
              启用智能切换：在用 key 达到阈值时，自动切换到优先级最高的可用 key
            </label>
            <div className="row">
              <Field label="触发阈值(%)：">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={cfg.auto_switch.trigger_percent}
                  onChange={(e) =>
                    setCfg({ ...cfg, auto_switch: { ...cfg.auto_switch, trigger_percent: Number(e.target.value) } })
                  }
                />
              </Field>
              <Field label="检测间隔(分钟)：">
                <input
                  type="number"
                  min={1}
                  value={cfg.auto_switch.interval_min}
                  onChange={(e) =>
                    setCfg({ ...cfg, auto_switch: { ...cfg.auto_switch, interval_min: Number(e.target.value) } })
                  }
                />
              </Field>
              <Btn onClick={saveAuto}>保存设置</Btn>
              <Btn primary onClick={smartNow} disabled={busy}>
                {busy ? "检测中…" : "立即检测并切换"}
              </Btn>
            </div>
          </>
        )}
      </div>

      <h3 className="section-title">各软件当前配置</h3>
      <div className="actual-list">
        {Object.entries(actual).map(([name, m]) => (
          <div className="actual-row" key={name}>
            <span className="actual-name">{name}</span>
            <span className="actual-keys">
              {Object.entries(m).map(([p, v]) => (
                <span key={p} className="actual-item">
                  {p}: {v.slice(0, 5)}…{v.slice(-4)}
                </span>
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------- Key 配置（核心表格） ----------------

export function MatrixPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [actual, setActual] = useState<Record<string, Record<string, string>>>({});
  const [sel, setSel] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const c = await api.getConfig();
      setCfg(c);
      setActual(await api.getActualKeys());
      const s: Record<string, string> = {};
      for (const t of c.targets) {
        for (const p of Object.keys(c.providers)) {
          s[`${t.name}::${p}`] = t.mapping[p] || "__none__";
        }
      }
      setSel(s);
    } catch (e) {
      msgErr(e);
    }
  };
  useEffect(() => {
    load();
  }, []);

  // ⚠️ 所有 hooks 必须放在条件 return 之前（否则组件在 cfg 从 null→有值时
  // hook 数量不一致，触发 React error #310 → 整棵组件树卸载 → 空白）
  const providerIds = useMemo(() => {
    const m: Record<string, string[]> = {};
    if (cfg) {
      for (const p of Object.keys(cfg.providers)) {
        m[p] = (cfg.providers[p]?.keys || []).map((k) => k.id);
      }
    }
    return m;
  }, [cfg]);

  if (!cfg) return <div className="page">加载中…</div>;

  const providers = Object.keys(cfg.providers);

  const save = async () => {
    setBusy(true);
    try {
      const mappings: Record<string, Record<string, string>> = {};
      for (const t of cfg.targets) {
        mappings[t.name] = {};
        for (const p of providers) {
          const v = sel[`${t.name}::${p}`];
          mappings[t.name][p] = v && v !== "__none__" ? v : "";
        }
      }
      const r = await api.applyTargets(mappings);
      const lines = r.results.map((x) => `${x.ok ? "✅" : "❌"} [${x.target}] ${x.provider ?? ""} ${x.msg}`);
      alert(lines.join("\n") + `\n\n⚠️ 需重启生效: ${r.restart.join("、") || "无"}`);
      await load();
    } catch (e) {
      msgErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h2 className="page-title">Key 配置</h2>
      <p className="page-sub">每个软件独立指定 Provider 用哪个 Key → 下拉选择 → 「保存并应用」</p>

      <table className="matrix">
        <thead>
          <tr>
            <th>软件</th>
            <th>当前生效 key</th>
            {providers.map((p) => (
              <th key={p}>{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cfg.targets.map((t) => (
            <tr key={t.name}>
              <td className="cell-name">{t.label || t.name}</td>
              <td className="cell-actual">
                {Object.entries(actual[t.name] || {}).map(([p, v]) => (
                  <div key={p} className="actual-item">
                    {p}: {v.slice(0, 5)}…{v.slice(-4)}
                  </div>
                ))}
              </td>
              {providers.map((p) => {
                const key = `${t.name}::${p}`;
                const ids = providerIds[p] || [];
                return (
                  <td key={p}>
                    <select
                      className="select"
                      value={sel[key] || "__none__"}
                      onChange={(e) => setSel((prev) => ({ ...prev, [key]: e.target.value }))}
                    >
                      {["__none__", ...ids].map((id) => (
                        <option key={id} value={id}>
                          {id === "__none__" ? "不使用" : id}
                        </option>
                      ))}
                    </select>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row">
        <Btn primary onClick={save} disabled={busy}>💾 保存并应用</Btn>
        <Btn onClick={load}>🔄 刷新实际状态</Btn>
      </div>
    </div>
  );
}

// ---------------- Provider 管理 ----------------

export function ProvidersPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [usageType, setUsageType] = useState("percent");

  const load = async () => setCfg(await api.getConfig());
  useEffect(() => {
    load();
  }, []);

  const add = async () => {
    try {
      const msg = await api.addProvider(name.trim(), baseUrl.trim(), usageType);
      msgOk(msg);
      setShowAdd(false);
      setName("");
      setBaseUrl("");
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  const del = async (p: string) => {
    if (!confirm(`删除 Provider「${p}」及其所有 key？`)) return;
    try {
      msgOk(await api.deleteProvider(p));
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  if (!cfg) return <div className="page">加载中…</div>;

  return (
    <div className="page">
      <h2 className="page-title">Provider 管理</h2>
      <p className="page-sub">API 渠道：添加新渠道（如 Kimi / GLM / OpenRouter）</p>

      <table className="matrix">
        <thead>
          <tr>
            <th>Provider</th>
            <th>Base URL</th>
            <th>用量类型</th>
            <th>Key 数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(cfg.providers).map(([p, pc]) => (
            <tr key={p}>
              <td className="cell-name">{p}</td>
              <td>{pc.base_url}</td>
              <td>{pc.usage_type}</td>
              <td>{pc.keys.length}</td>
              <td>
                <Btn danger onClick={() => del(p)}>删除</Btn>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row">
        <Btn primary onClick={() => setShowAdd(true)}>➕ 添加 Provider</Btn>
        <Btn onClick={load}>🔄 刷新</Btn>
      </div>

      {showAdd && (
        <Modal title="添加 Provider" onClose={() => setShowAdd(false)}>
          <Field label="Provider 标识（英文，如 kimi）：">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="kimi" />
          </Field>
          <Field label="Base URL：">
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.kimi.com/v1" />
          </Field>
          <Field label="用量类型：">
            <select value={usageType} onChange={(e) => setUsageType(e.target.value)}>
              <option value="percent">percent（查 /usage 百分比）</option>
              <option value="balance">balance（查 /user/balance 余额）</option>
            </select>
          </Field>
          <div className="row right">
            <Btn primary onClick={add}>确定</Btn>
            <Btn onClick={() => setShowAdd(false)}>取消</Btn>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------- Key 池（优先级排序） ----------------

export function KeysPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [selKey, setSelKey] = useState<string | null>(null); // `${provider}::${keyId}`
  const [showAdd, setShowAdd] = useState(false);
  const [addProvider, setAddProvider] = useState("");
  const [addId, setAddId] = useState("");
  const [addValue, setAddValue] = useState("");
  const [addNote, setAddNote] = useState("");
  // 编辑状态：null = 未编辑；非 null = 正在编辑某 key（provider,id）
  const [editing, setEditing] = useState<{ provider: string; id: string } | null>(null);
  const [editProvider, setEditProvider] = useState("");
  const [editId, setEditId] = useState("");
  const [editValue, setEditValue] = useState("");
  const [editNote, setEditNote] = useState("");

  const load = async () => setCfg(await api.getConfig());
  useEffect(() => {
    load();
  }, []);

  // 打开编辑框：填入当前 key 的 provider/标识/值/备注
  const openEdit = (provider: string, id: string) => {
    const k = cfg?.providers[provider]?.keys.find((x) => x.id === id);
    setEditing({ provider, id });
    setEditProvider(provider);
    setEditId(id);
    setEditValue(k?.key ?? "");
    setEditNote(k?.note ?? "");
  };

  // 保存编辑
  const saveEdit = async () => {
    if (!editing) return;
    try {
      msgOk(
        await api.editKey(
          editing.provider,
          editing.id,
          editProvider,
          editId.trim(),
          editValue.trim(),
          editNote.trim(),
        ),
      );
      setEditing(null);
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  const move = async (direction: string) => {
    if (!selKey) return alert("请先选中要调整的 Key");
    const [p, kid] = selKey.split("::");
    try {
      msgOk(await api.moveKey(p, kid, direction));
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  const del = async () => {
    if (!selKey) return alert("请先选中要删除的 Key");
    const [p, kid] = selKey.split("::");
    if (!confirm(`删除 ${p}/${kid}？引用它的应用会自动改为不使用`)) return;
    try {
      msgOk(await api.deleteKey(p, kid));
      setSelKey(null);
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  const add = async () => {
    try {
      msgOk(await api.addKey(addProvider, addId.trim(), addValue.trim(), addNote.trim()));
      setShowAdd(false);
      setAddId("");
      setAddValue("");
      setAddNote("");
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  if (!cfg) return <div className="page">加载中…</div>;
  const providers = Object.keys(cfg.providers);

  return (
    <div className="page">
      <h2 className="page-title">Key 池</h2>
      <p className="page-sub">
        排序 = 设置优先级（越靠上越优先，智能切换优先选用）。选中 Key 后点 ↑↓ 调整。
      </p>

      <table className="matrix">
        <thead>
          <tr>
            <th>优先级</th>
            <th>Provider</th>
            <th>Key 标识</th>
            <th>Key（前缀…）</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {providers.flatMap((p) => {
            const pc = cfg.providers[p];
            return pc.keys.map((k, i) => {
              const key = `${p}::${k.id}`;
              return (
                <tr
                  key={key}
                  className={selKey === key ? "selected" : ""}
                  onClick={() => setSelKey(key)}
                >
                  <td className="cell-prio">{i + 1}</td>
                  <td>{p}</td>
                  <td>{k.id}</td>
                  <td>
                    {k.key ? `${k.key.slice(0, 8)}…${k.key.slice(-4)}` : "(空)"}
                  </td>
                  <td>{k.note}</td>
                  <td>
                    <button
                      className="btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        openEdit(p, k.id);
                      }}
                    >
                      ✏️ 编辑
                    </button>
                  </td>
                </tr>
              );
            });
          })}
        </tbody>
      </table>

      <div className="row">
        <Btn primary onClick={() => setShowAdd(true)}>➕ 添加 API Key</Btn>
        <Btn danger onClick={del}>➖ 删除选中 Key</Btn>
        <Btn onClick={() => move("up")}>↑ 提高优先级（前移）</Btn>
        <Btn onClick={() => move("down")}>↓ 降低优先级（后移）</Btn>
        <Btn onClick={load}>🔄 刷新</Btn>
      </div>

      {showAdd && (
        <Modal title="添加 API Key" onClose={() => setShowAdd(false)}>
          <Field label="所属 Provider：">
            <select
              value={addProvider}
              onChange={(e) => {
                setAddProvider(e.target.value);
                const n = cfg.providers[e.target.value]?.keys.length ?? 0;
                setAddId(`${e.target.value}-${n + 1}`);
              }}
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Key 标识：">
            <input value={addId} onChange={(e) => setAddId(e.target.value)} />
          </Field>
          <Field label="API Key 值：">
            <input value={addValue} onChange={(e) => setAddValue(e.target.value)} />
          </Field>
          <Field label="备注：">
            <input value={addNote} onChange={(e) => setAddNote(e.target.value)} placeholder="谁在用/用途" />
          </Field>
          <div className="row right">
            <Btn primary onClick={add}>确定</Btn>
            <Btn onClick={() => setShowAdd(false)}>取消</Btn>
          </div>
        </Modal>
      )}

      {editing && (
        <Modal title="编辑 API Key" onClose={() => setEditing(null)}>
          <Field label="所属 Provider：">
            <select
              value={editProvider}
              onChange={(e) => setEditProvider(e.target.value)}
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Key 标识：">
            <input value={editId} onChange={(e) => setEditId(e.target.value)} />
          </Field>
          <Field label="API Key 值：">
            <input value={editValue} onChange={(e) => setEditValue(e.target.value)} />
          </Field>
          <Field label="备注：">
            <input value={editNote} onChange={(e) => setEditNote(e.target.value)} placeholder="谁在用/用途" />
          </Field>
          <p className="page-sub">
            修改 Provider 或标识后，引用该 key 的应用映射会同步迁移到新位置。同 Provider 内修改保持原优先级。
          </p>
          <div className="row right">
            <Btn primary onClick={saveEdit}>保存</Btn>
            <Btn onClick={() => setEditing(null)}>取消</Btn>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------- 应用管理 ----------------

export function AppsPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [adapters, setAdapters] = useState<{ name: string; description: string }[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  // 表单
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [adapter, setAdapter] = useState("");
  const [params, setParams] = useState<Record<string, string>>({});
  const [mapping, setMapping] = useState<Record<string, string>>({});

  const load = async () => {
    setCfg(await api.getConfig());
    setAdapters(await api.listAdapters());
  };
  useEffect(() => {
    load();
  }, []);

  const add = async () => {
    try {
      const m: Record<string, string> = {};
      for (const [p, v] of Object.entries(mapping)) {
        m[p] = v && v !== "__none__" ? v : "";
      }
      const msg = await api.addTarget({
        name: name.trim(),
        label: label.trim() || name.trim(),
        adapter,
        ...(params.env ? { env: params.env } : {}),
        ...(params.path ? { path: params.path } : {}),
        ...(params.key_path ? { key_path: params.key_path } : {}),
        ...(params.key_name ? { key_name: params.key_name } : {}),
        ...(params.pattern ? { pattern: params.pattern } : {}),
        ...(params.replacement ? { replacement: params.replacement } : {}),
        mapping: m,
      });
      msgOk(msg);
      setShowAdd(false);
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  const del = async (n: string) => {
    if (!confirm(`删除应用「${n}」？（只移除管理，不删除软件配置）`)) return;
    try {
      msgOk(await api.deleteTarget(n));
      await load();
    } catch (e) {
      msgErr(e);
    }
  };

  if (!cfg) return <div className="page">加载中…</div>;
  const providers = Object.keys(cfg.providers);

  // 适配器参数表单定义
  const adapterFields: Record<string, [string, string][]> = {
    env_var: [["env", "环境变量名（如 OPENAI_API_KEY）"]],
    file_json: [
      ["path", "配置文件完整路径"],
      ["key_path", "JSON 点路径（如 opencode-go.key）"],
    ],
    file_env: [
      ["path", "配置文件完整路径"],
      ["key_name", "KEY=VALUE 键名（如 API_KEY）"],
    ],
    file_regex: [
      ["path", "配置文件完整路径"],
      ["pattern", "正则（含 1 个捕获组）"],
    ],
  };

  return (
    <div className="page">
      <h2 className="page-title">应用管理</h2>
      <p className="page-sub">把新软件接入管理：选适配器 → 指定用哪个 Key</p>

      <table className="matrix">
        <thead>
          <tr>
            <th>标识</th>
            <th>显示名</th>
            <th>适配器</th>
            <th>映射</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {cfg.targets.map((t) => (
            <tr key={t.name}>
              <td className="cell-name">{t.name}</td>
              <td>{t.label}</td>
              <td>{t.adapter}</td>
              <td>
                {Object.entries(t.mapping)
                  .filter(([, v]) => v)
                  .map(([p, v]) => `${p}=${v}`)
                  .join(", ") || "(未指定)"}
              </td>
              <td>
                <Btn danger onClick={() => del(t.name)}>删除</Btn>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row">
        <Btn primary onClick={() => setShowAdd(true)}>➕ 添加应用</Btn>
        <Btn onClick={load}>🔄 刷新</Btn>
      </div>
      <p className="page-sub">
        适配器说明：pi=pi工具 / env_var=环境变量 / openchatcut / workbuddy / codex=codex-router / file_json=JSON文件 / file_env=.env文件 / file_regex=正则替换
      </p>

      {showAdd && (
        <Modal title="添加应用" onClose={() => setShowAdd(false)}>
          <Field label="应用标识（英文，如 my_app）：">
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="显示名：">
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="我的软件" />
          </Field>
          <Field label="适配器类型：">
            <select
              value={adapter}
              onChange={(e) => {
                setAdapter(e.target.value);
                setParams({});
              }}
            >
              {adapters.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name} — {a.description}
                </option>
              ))}
            </select>
          </Field>
          {adapterFields[adapter]?.map(([k, tip]) => (
            <Field key={k} label={`${k}（${tip}）：`}>
              <input
                value={params[k] || ""}
                onChange={(e) => setParams({ ...params, [k]: e.target.value })}
              />
            </Field>
          ))}
          <div className="field">
            <span>此应用使用哪些 Provider 的 Key：</span>
            {providers.map((p) => (
              <div className="row map-row" key={p}>
                <span className="map-label">{p}:</span>
                <select
                  value={mapping[p] || "__none__"}
                  onChange={(e) => setMapping({ ...mapping, [p]: e.target.value })}
                >
                  {["__none__", ...(cfg.providers[p]?.keys.map((k) => k.id) || [])].map((id) => (
                    <option key={id} value={id}>
                      {id === "__none__" ? "不使用" : id}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <div className="row right">
            <Btn primary onClick={add}>确定</Btn>
            <Btn onClick={() => setShowAdd(false)}>取消</Btn>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------- 设置 ----------------

export function SettingsPage() {
  const [version, setVersion] = useState("");
  const [configPath, setConfigPath] = useState("");
  useEffect(() => {
    api.version().then(setVersion).catch(() => {});
    // 配置路径由 Rust 端决定，这里显示提示
    setConfigPath("%APPDATA%\\KeySwitch\\config.toml");
  }, []);

  return (
    <div className="page">
      <h2 className="page-title">设置</h2>
      <p className="page-sub">配置文件、日志与使用说明</p>

      <div className="card info-card">
        <div className="info-line">
          <b>配置文件：</b>
          <span>{configPath}</span>
        </div>
        <div className="info-line">
          <b>版本：</b>
          <span>{version || "…"}</span>
        </div>
        <div className="info-line">
          <b>说明：</b>
          <span>配置为 TOML 格式，可从 Python 版一键迁移（见 tools/migrate_config.py）</span>
        </div>
      </div>

      <div className="row">
        <Btn primary onClick={() => api.openPath("config_dir").catch(msgErr)}>
          📂 打开配置目录
        </Btn>
      </div>
    </div>
  );
}
