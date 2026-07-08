"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { DangerZone } from "./danger-zone";

const settingsSchema = z.object({
  displayName: z
    .string()
    .min(2, "Display name must be at least 2 characters")
    .max(50),
  bio: z.string().max(160, "Bio must be 160 characters or fewer").optional(),
  theme: z.enum(["light", "dark", "system"]),
  defaultView: z.enum(["grid", "list", "tree"]),
  emailOnUpload: z.boolean(),
  warnNearQuota: z.boolean(),
  quotaThreshold: z
    .string()
    .regex(/^\d+$/, "Must be a number")
    .refine((v) => {
      const n = Number(v);
      return n >= 50 && n <= 95;
    }, "Must be between 50 and 95"),
});

type SettingsValues = z.infer<typeof settingsSchema>;

const defaultValues: SettingsValues = {
  displayName: "Anonymous",
  bio: "",
  theme: "system",
  defaultView: "tree",
  emailOnUpload: false,
  warnNearQuota: true,
  quotaThreshold: "80",
};

export function SettingsForm() {
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues,
  });

  const onSubmit = async (values: SettingsValues) => {
    setSubmitting(true);
    // Demo-only — wire to a real API endpoint when you add one
    await new Promise((r) => setTimeout(r, 400));
    setSubmitting(false);
    toast.success("Settings saved", {
      description: `Display name set to "${values.displayName}"`,
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {/* Profile */}
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Profile</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <FormField
              control={form.control}
              name="displayName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display name</FormLabel>
                  <FormControl>
                    <Input placeholder="Your name" {...field} />
                  </FormControl>
                  <FormDescription>
                    Shown in activity logs and share links.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="bio"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Bio</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="A short description of this workspace"
                      className="resize-none"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Max 160 characters.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* Preferences */}
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Preferences</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-6">
            <FormField
              control={form.control}
              name="theme"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Theme</FormLabel>
                  <FormControl>
                    <RadioGroup
                      onValueChange={field.onChange}
                      value={field.value}
                      className="flex gap-6"
                    >
                      {(["light", "dark", "system"] as const).map((t) => (
                        <label
                          key={t}
                          className="flex items-center gap-2 text-sm capitalize cursor-pointer"
                        >
                          <RadioGroupItem value={t} />
                          {t}
                        </label>
                      ))}
                    </RadioGroup>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="defaultView"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Default file view</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger className="w-60">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="tree">Tree</SelectItem>
                      <SelectItem value="list">List</SelectItem>
                      <SelectItem value="grid">Grid</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Applied when you open the Files page.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="emailOnUpload"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-md border border-border p-3">
                  <div className="space-y-0.5">
                    <FormLabel>Email me on every upload</FormLabel>
                    <FormDescription>
                      You&apos;ll get a receipt for each successful upload.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="warnNearQuota"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start gap-3">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="grid gap-1.5 leading-none">
                    <FormLabel>Warn me when approaching quota</FormLabel>
                    <FormDescription>
                      Shows a banner once usage crosses your threshold.
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="quotaThreshold"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Quota warning threshold (%)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={50}
                      max={95}
                      className="w-32 font-mono tabular-nums"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Between 50 and 95.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <DangerZone />

        {/* Action bar */}
        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => form.reset(defaultValues)}
          >
            Reset
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
