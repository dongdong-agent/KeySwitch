// KeySwitch 前端 API 封装（tauri invoke → Rust 命令）
// ⚠️ Tauri 2 的 #[tauri::command] 默认把参数名按 camelCase 与前端匹配
//（Rust 参数 snake_case key_id ↔ 前端 keyId，由宏自动转换）——前端必须传 camelCase。

import { invoke } from "@tauri-apps/api/core";

export interface KeyItem {
  id: string;
  key: string;
  note: string;
  promo_url?: string | null;
  reward?: string | null;
}
export interface Provider {
  base_url: string;
  usage_type: string;
  keys: KeyItem[];
}
export interface Target {
  name: string;
  label: string;
  adapter: string;
  env?: string;
  path?: string;
  key_path?: string;
  key_name?: string;
  pattern?: string;
  replacement?: string;
  mapping: Record<string, string>;
}
export interface AutoSwitch {
  enabled: boolean;
  interval_min: number;
  trigger_percent: number;
}
export interface Config {
  thresholds?: Record<string, Record<string, number>>;
  providers: Record<string, Provider>;
  targets: Target[];
  auto_switch: AutoSwitch;
}
export interface UsageInfo {
  kind: string;
  percent: number | null;
  weekly: number | null;
  monthly: number | null;
  balance: number | null;
  status: string;
  detail: string;
  // 注意：Tauri 命令返回值字段是 snake_case（与入参 camelCase 相反）
  rolling_reset: string | null;
  weekly_reset: string | null;
  monthly_reset: string | null;
}
export interface KeyStatus {
  provider: string;
  id: string;
  key_prefix: string;
  note: string;
  usage: UsageInfo | null;
}
export interface WriteResult {
  ok: boolean;
  msg: string;
  provider?: string;
  target?: string;
}
export interface ApplyResult {
  results: WriteResult[];
  restart: string[];
}
export interface UseKeyResult {
  provider: string;
  key_id: string;
  targets: string[];
  failed: string[];
  restart: string[];
  error: string;
}
export interface SwitchEvent {
  provider: string;
  to_provider: string;
  from: string;
  to: string;
  targets: string[];
  failed: string[];
}
export interface SmartResult {
  switches: SwitchEvent[];
  exhausted: string[];
  checked: number;
  query_failed: string[];
}
export interface AdapterInfo {
  name: string;
  description: string;
}

export const api = {
  version: () => invoke<string>("version"),
  getConfig: () => invoke<Config>("get_config"),
  saveConfig: (cfg: Config) => invoke<void>("save_config_front", { cfg }),
  getStatus: (force?: boolean) => invoke<KeyStatus[]>("get_status", force ? { force: true } : {}),
  getActualKeys: () => invoke<Record<string, Record<string, string>>>("get_actual_keys"),
  listAdapters: () => invoke<AdapterInfo[]>("list_adapters"),
  applyTargets: (newMappings: Record<string, Record<string, string>>) =>
    invoke<ApplyResult>("apply_targets", { newMappings }),
  useKey: (provider: string, keyId: string) =>
    invoke<UseKeyResult>("use_key", { provider, keyId }),
  smartCheck: (trigger?: number) =>
    invoke<SmartResult>("smart_check", { trigger }),
  saveAutoSettings: (enabled: boolean, triggerPercent: number, intervalMin: number) =>
    invoke<void>("save_auto_settings", { enabled, triggerPercent, intervalMin }),
  addProvider: (name: string, baseUrl: string, usageType: string) =>
    invoke<string>("add_provider", { name, baseUrl, usageType }),
  deleteProvider: (name: string) => invoke<string>("delete_provider", { name }),
  addKey: (provider: string, keyId: string, keyValue: string, note: string, promoUrl?: string, reward?: string) =>
    invoke<string>("add_key", { provider, keyId, keyValue, note, promoUrl, reward }),
  deleteKey: (provider: string, keyId: string) =>
    invoke<string>("delete_key", { provider, keyId }),
  editKey: (provider: string, oldId: string, newProvider: string, newId: string, newValue: string, newNote: string, promoUrl?: string, reward?: string) =>
    invoke<string>("edit_key", { provider, oldId, newProvider, newId, newValue, newNote, promoUrl, reward }),
  moveKey: (provider: string, keyId: string, direction: string) =>
    invoke<string>("move_key", { provider, keyId, direction }),
  addTarget: (t: Omit<Target, "mapping"> & { mapping: Record<string, string> }) =>
    invoke<string>("add_target", {
      name: t.name,
      label: t.label,
      adapter: t.adapter,
      env: t.env,
      path: t.path,
      keyPath: t.key_path,
      keyName: t.key_name,
      pattern: t.pattern,
      replacement: t.replacement,
      mapping: t.mapping,
    }),
  deleteTarget: (name: string) => invoke<string>("delete_target", { name }),
  openPath: (kind: string) => invoke<void>("open_path", { kind }),
};
