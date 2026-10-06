"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useSettings, useUpdateSettings } from "@/lib/queries";
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
  const { data: settings, isPending: isLoadingSettings } = useSettings();
  const updateSettings = useUpdateSettings();

  const form = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues,
    values: settings ? {
      displayName: settings.display_name || "",
      bio: settings.bio || "",
      theme: settings.theme,
      defaultView: settings.default_view,
      emailOnUpload: settings.email_on_upload,
      warnNearQuota: settings.warn_near_quota,
      quotaThreshold: String(settings.quota_threshold),
    } : undefined,
  });

  const onSubmit = (values: SettingsValues) => {
    updateSettings.mutate(
      {
        display_name: values.displayName || null,
        bio: values.bio || null,
        theme: values.theme,
        default_view: values.defaultView,
        email_on_upload: values.emailOnUpload,
        warn_near_quota: values.warnNearQuota,
        quota_threshold: Number(values.quotaThreshold),
      },
      {
        onSuccess: () => {
          toast.success("Settings saved");
          // Reset explicitly so form's isDirty state clears (since RHF tracks dirty
          // state relative to the last values/defaultValues). It will update automatically
          // via `values` once the invalidation refetches the query, but immediate reset
          // makes the UI snappy.
          form.reset(values);
        },
        onError: (err) => {
          toast.error("Failed to save settings", {
            description: err.message,
          });
        },
      }
    );
  };

  if (isLoadingSettings) {
    return (
      <div className="flex h-[400px] items-center justify-center rounded-xl border border-border">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <p className="text-sm">Loading settings...</p>
        </div>
      </div>
    );
  }

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
                      placeholder="A short bio"
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
        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => form.reset()}
            disabled={!form.formState.isDirty || updateSettings.isPending}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            disabled={!form.formState.isDirty || updateSettings.isPending}
          >
            {updateSettings.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save changes
          </Button>
        </div>
      </form>
    </Form>
  );
}
