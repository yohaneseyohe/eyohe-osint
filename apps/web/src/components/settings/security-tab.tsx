"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useUsers } from "@/lib/queries";
import type { UserOut } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { QueryState, EmptyState } from "@/components/shared/states";

function ChangePassword() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const change = useMutation({
    mutationFn: () => apiPost("/auth/password", { current_password: form.current, new_password: form.next }),
    onSuccess: () => { setForm({ current: "", next: "", confirm: "" }); toast.success("Password changed"); },
    onError: (e) => toast.error("Could not change password", errorMessage(e)),
  });
  const mismatch = form.confirm.length > 0 && form.next !== form.confirm;
  return (
    <Card>
      <CardHeader><CardTitle>Change password</CardTitle></CardHeader>
      <CardContent>
        <form className="grid max-w-xl gap-3 md:grid-cols-3" onSubmit={(e) => { e.preventDefault(); if (!mismatch) change.mutate(); }}>
          <div className="space-y-1"><Label htmlFor="pw-cur">Current</Label><Input id="pw-cur" type="password" autoComplete="current-password" required value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="pw-new">New</Label><Input id="pw-new" type="password" autoComplete="new-password" required minLength={12} value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="pw-conf">Confirm</Label><Input id="pw-conf" type="password" autoComplete="new-password" required value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} aria-invalid={mismatch} /></div>
          {mismatch ? <p className="text-xs text-danger md:col-span-3">Passwords do not match.</p> : null}
          <div className="md:col-span-3"><Button type="submit" size="sm" loading={change.isPending} disabled={mismatch}>Update password</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}

function CreateUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", username: "", display_name: "", password: "", role: "analyst" });
  const create = useMutation({
    mutationFn: () => apiPost<UserOut>("/auth/users", form),
    onSuccess: (u) => { qc.invalidateQueries({ queryKey: qk.users }); toast.success("User created", u.username); onOpenChange(false); setForm({ email: "", username: "", display_name: "", password: "", role: "analyst" }); },
    onError: (e) => toast.error("Could not create user", errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Create user" description="Analysts can run investigations and review evidence; viewers are read-only.">
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <DialogBody>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1"><Label htmlFor="u-email">Email</Label><Input id="u-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
              <div className="space-y-1"><Label htmlFor="u-user">Username</Label><Input id="u-user" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
              <div className="space-y-1"><Label htmlFor="u-display">Display name</Label><Input id="u-display" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
              <div className="space-y-1"><Label htmlFor="u-pass">Initial password</Label><Input id="u-pass" type="password" required minLength={12} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
              <div className="space-y-1">
                <Label htmlFor="u-role">Role</Label>
                <Select value={form.role} onValueChange={(role) => setForm({ ...form, role })}>
                  <SelectTrigger id="u-role"><SelectValue /></SelectTrigger>
                  <SelectContent>{["admin", "analyst", "viewer"].map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" loading={create.isPending}>Create user</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function SecurityTab({ isAdmin }: { isAdmin: boolean }) {
  const users = useUsers(isAdmin);
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-6">
      <ChangePassword />
      {isAdmin ? (
        <Card>
          <CardHeader><CardTitle>Users</CardTitle><Button size="xs" onClick={() => setOpen(true)}><Plus /> Create user</Button></CardHeader>
          <CardContent className="p-0">
            <QueryState query={users} rows={3} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No users" className="m-4" />}>
              {(items) => (
                <Table>
                  <TableHeader><TableRow><TableHead>User</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead>Active</TableHead><TableHead>Last login</TableHead><TableHead>Created</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {items.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell><span className="text-fg">{u.display_name || u.username}</span> <Mono className="text-fg-subtle">@{u.username}</Mono></TableCell>
                        <TableCell><Mono className="text-fg-muted">{u.email}</Mono></TableCell>
                        <TableCell className="text-xs uppercase text-accent-bright">{u.role}</TableCell>
                        <TableCell className="text-xs">{u.is_active ? "yes" : "no"}</TableCell>
                        <TableCell><Mono className="text-fg-subtle">{u.last_login_at ? formatTs(u.last_login_at) : "never"}</Mono></TableCell>
                        <TableCell><Mono className="text-fg-subtle">{formatTs(u.created_at)}</Mono></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </QueryState>
          </CardContent>
          <CreateUserDialog open={open} onOpenChange={setOpen} />
        </Card>
      ) : <p className="text-xs text-fg-subtle">User management is available to administrators.</p>}
    </div>
  );
}
