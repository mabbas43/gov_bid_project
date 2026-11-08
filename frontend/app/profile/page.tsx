"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Plus, Save, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorCard } from "@/components/error-card";
import { api, formatPkr, type PastProject, type Profile, type Registrations } from "@/lib/api";

const REGISTRATIONS: { key: keyof Registrations; label: string; hint: string }[] = [
  { key: "ntn", label: "NTN", hint: "National Tax Number" },
  { key: "atl_status", label: "ATL status", hint: "active or inactive" },
  { key: "secp", label: "SECP", hint: "Company registration no." },
  { key: "pseb", label: "PSEB", hint: "Registration no." },
  { key: "pec_category", label: "PEC category", hint: "e.g. C-5. Blank if none" },
];

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newCapability, setNewCapability] = useState("");

  const load = useCallback(() => {
    setError(null);
    api<Profile>("/profile").then(setProfile).catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  if (error && !profile) return <ErrorCard message={error} onRetry={load} />;
  if (!profile) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const update = (patch: Partial<Profile>) => {
    setSaved(false);
    setProfile({ ...profile, ...patch });
  };
  const setRegistration = (key: keyof Registrations, value: string) =>
    update({ registrations: { ...profile.registrations, [key]: value.trim() === "" ? null : value } });
  const setProject = (i: number, patch: Partial<PastProject>) =>
    update({ past_projects: profile.past_projects.map((p, j) => (i === j ? { ...p, ...patch } : p)) });
  const addCapability = () => {
    const value = newCapability.trim();
    if (value && !profile.capabilities.includes(value)) update({ capabilities: [...profile.capabilities, value] });
    setNewCapability("");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      setProfile(await api<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) }));
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const placeholder = profile.registrations.ntn === "0000000-0";

  return (
    <form onSubmit={save} className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Company Profile</h1>
          <p className="text-sm text-muted-foreground">Eligibility checks and bid packs use these details.</p>
        </div>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="inline-flex items-center gap-1 text-sm text-emerald-700" role="status">
              <CheckCircle2 className="size-4" /> Saved
            </span>
          )}
          <Button type="submit" disabled={saving}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />} Save
          </Button>
        </div>
      </div>

      {placeholder && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          This is sample data. Replace the registration numbers and past projects with your own before using a bid pack.
        </p>
      )}
      {error && <ErrorCard message={error} />}

      <Card className="gap-4 p-5">
        <h2 className="font-semibold">Company</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="name" label="Company name">
            <Input id="name" required value={profile.name} onChange={(e) => update({ name: e.target.value })} />
          </Field>
          <Field id="city" label="City">
            <Input id="city" required value={profile.city} onChange={(e) => update({ city: e.target.value })} />
          </Field>
          <Field id="team" label="Team size">
            <Input id="team" type="number" min={1} required value={profile.team_size} onChange={(e) => update({ team_size: Number(e.target.value) })} />
          </Field>
          <Field id="years" label="Years in business">
            <Input id="years" type="number" min={0} required value={profile.years_in_business} onChange={(e) => update({ years_in_business: Number(e.target.value) })} />
          </Field>
          <Field id="turnover" label={`Annual turnover in PKR (${formatPkr(profile.annual_turnover_pkr)})`}>
            <Input id="turnover" type="number" min={0} required value={profile.annual_turnover_pkr} onChange={(e) => update({ annual_turnover_pkr: Number(e.target.value) })} />
          </Field>
        </div>
      </Card>

      <Card className="gap-3 p-5">
        <h2 className="font-semibold">Capabilities</h2>
        <div className="flex flex-wrap gap-2">
          {profile.capabilities.map((c) => (
            <span key={c} className="inline-flex items-center gap-1 rounded-full bg-emerald-100 py-1 pr-1.5 pl-3 text-sm text-emerald-900">
              {c}
              <button type="button" aria-label={`Remove ${c}`} className="rounded-full p-0.5 hover:bg-emerald-200" onClick={() => update({ capabilities: profile.capabilities.filter((x) => x !== c) })}>
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            aria-label="New capability"
            placeholder="Add a capability, e.g. ERP"
            value={newCapability}
            onChange={(e) => setNewCapability(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCapability();
              }
            }}
          />
          <Button type="button" variant="outline" onClick={addCapability}>Add</Button>
        </div>
      </Card>

      <Card className="gap-4 p-5">
        <h2 className="font-semibold">Registrations</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {REGISTRATIONS.map(({ key, label, hint }) => (
            <Field key={key} id={key} label={label}>
              <Input id={key} placeholder={hint} value={profile.registrations[key] ?? ""} onChange={(e) => setRegistration(key, e.target.value)} />
            </Field>
          ))}
        </div>
      </Card>

      <Card className="gap-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Past projects</h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => update({ past_projects: [...profile.past_projects, { title: "", client: "", value_pkr: 0, year: new Date().getFullYear() }] })}
          >
            <Plus className="size-3.5" /> Add project
          </Button>
        </div>
        <ul className="space-y-3">
          {profile.past_projects.map((p, i) => (
            <li key={i} className="grid items-end gap-2 rounded-lg border p-3 sm:grid-cols-[2fr_1.4fr_1fr_0.7fr_auto]">
              <Field id={`title-${i}`} label="Title">
                <Input id={`title-${i}`} required value={p.title} onChange={(e) => setProject(i, { title: e.target.value })} />
              </Field>
              <Field id={`client-${i}`} label="Client">
                <Input id={`client-${i}`} required value={p.client} onChange={(e) => setProject(i, { client: e.target.value })} />
              </Field>
              <Field id={`value-${i}`} label="Value (PKR)">
                <Input id={`value-${i}`} type="number" min={0} required value={p.value_pkr} onChange={(e) => setProject(i, { value_pkr: Number(e.target.value) })} />
              </Field>
              <Field id={`year-${i}`} label="Year">
                <Input id={`year-${i}`} type="number" required value={p.year} onChange={(e) => setProject(i, { year: Number(e.target.value) })} />
              </Field>
              <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${p.title || "project"}`} onClick={() => update({ past_projects: profile.past_projects.filter((_, j) => j !== i) })}>
                <Trash2 className="size-4 text-red-600" />
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </form>
  );
}
