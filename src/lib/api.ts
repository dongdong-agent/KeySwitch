// KeySwitch 前端 API 封装（tauri invoke → Rust 命令）

import { invoke } from "@tauri-apps/api/core";

export interface KeyItem {
  id: string;
  key: string;
  note: string;
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
export interface SwitchEvent {
  provider: string;
  from: string;
  to: string;
  targets: string[];
  failed: string[];
}
export interface SmartResult {
  switches: SwitchEvent[];
  exhausted: string[];
  checked: number;
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
  smartCheck: (trigger?: number) =>
    invoke<SmartResult>("smart_check", { trigger }),
  saveAutoSettings: (enabled: boolean, triggerPercent: number, intervalMin: number) =>
    invoke<void>("save_auto_settings", { enabled, trigger_percent: triggerPercent, interval_min: intervalMin }),
  addProvider: (name: string, baseUrl: string, usageType: string) =>
    invoke<string>("add_provider", { name, base_url: baseUrl, usage_type: usageType }),
  deleteProvider: (name: string) => invoke<string>("delete_provider", { name }),
  addKey: (provider: string, keyId: string, keyValue: string, note: string) =>
    invoke<string>("add_key", { provider, key_id: keyId, key_value: keyValue, note }),
  deleteKey: (provider: string, keyId: string) =>
    invoke<string>("delete_key", { provider, key_id: keyId }),
  editKey: (provider: string, oldId: string, newProvider: string, newId: string, newValue: string, newNote: string) =>
    invoke<string>("edit_key", { provider, old_id: oldId, new_provider: newProvider, new_id: newId, new_value: newValue, new_note: newNote }),
  moveKey: (provider: string, keyId: string, direction: string) =>
    invoke<string>("move_key", { provider, key_id: keyId, direction }),
  addTarget: (t: Omit<Target, "mapping"> & { mapping: Record<string, string> }) =>
    invoke<string>("add_target", { ...t }),
  deleteTarget: (name: string) => invoke<string>("delete_target", { name }),
  openPath: (kind: string) => invoke<void>("open_path", { kind }),
};
