"use client";

import { useEffect } from "react";
import { Check, CreditCard, Lock, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import { ApiError } from "@/lib/api-client";
import {
  useCheckout,
  useEntitlements,
  usePlans,
  usePortal,
  useProPreview,
  useSubscription,
} from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const UNAVAILABLE_MSG =
  "Billing is temporarily unavailable. Please try again later.";

function billingErrorToast(err: ApiError) {
  toast.error(
    err.status === 503 ? UNAVAILABLE_MSG : "Something went wrong. Please try again.",
  );
}

function priceLabel(cents: number, interval: string): string {
  if (cents === 0) return "Free";
  return `$${(cents / 100).toFixed(0)}/${interval}`;
}

export default function BillingPage() {
  const { user } = useAuth();
  const enabled = !!user;
  const plans = usePlans();
  const subscription = useSubscription(enabled);
  const entitlements = useEntitlements(enabled);
  const proPreview = useProPreview(enabled);
  const checkout = useCheckout();
  const portal = usePortal();

  // Surface the ?checkout=success|cancelled param Stripe redirects back with,
  // then strip it so a refresh doesn't re-toast. Read from the URL directly to
  // avoid a Suspense boundary just for one query param.
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get("checkout");
    if (status === "success") {
      toast.success("Subscription updated — welcome aboard!");
    } else if (status === "cancelled") {
      toast.info("Checkout cancelled — no changes made.");
    }
    if (status) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const currentRank = entitlements.data?.rank ?? 0;
  const currentTier = entitlements.data?.tier ?? "free";
  const hasCustomer = !!subscription.data?.stripe_customer_id;

  function onUpgrade(planId: string) {
    checkout.mutate(planId, { onError: billingErrorToast });
  }

  function onManage() {
    portal.mutate(undefined, { onError: billingErrorToast });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Billing</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Manage your subscription.
            {subscription.data?.test_mode && (
              <>
                {" "}
                Test mode uses card{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">
                  4242 4242 4242 4242
                </code>
                .
              </>
            )}
          </p>
        </div>
        {hasCustomer && (
          <Button variant="outline" onClick={onManage} disabled={portal.isPending}>
            <CreditCard className="mr-2 h-4 w-4" />
            {portal.isPending ? "Opening…" : "Manage billing"}
          </Button>
        )}
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Current plan:</span>
        <Badge variant={currentRank > 0 ? "default" : "secondary"} data-testid="current-plan">
          {currentTier.toUpperCase()}
        </Badge>
        {subscription.data?.cancel_at_period_end && (
          <span className="text-xs text-muted-foreground">(cancels at period end)</span>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {plans.isPending && (
          <p className="text-sm text-muted-foreground">Loading plans…</p>
        )}
        {plans.data?.map((plan) => {
          const isCurrent = plan.rank === currentRank;
          const isFree = plan.id === "free";
          return (
            <Card
              key={plan.id}
              className={isCurrent ? "border-primary" : ""}
              data-testid={`plan-card-${plan.id}`}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{plan.name}</CardTitle>
                  {isCurrent && <Badge>Current</Badge>}
                </div>
                <CardDescription className="text-lg font-semibold text-foreground">
                  {priceLabel(plan.price_cents, plan.interval)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                {isCurrent ? (
                  <Button variant="outline" className="w-full" disabled>
                    Current plan
                  </Button>
                ) : isFree ? (
                  <Button variant="ghost" className="w-full" disabled>
                    Included
                  </Button>
                ) : (
                  <Button
                    className="w-full"
                    onClick={() => onUpgrade(plan.id)}
                    disabled={checkout.isPending}
                    data-testid={`upgrade-${plan.id}`}
                  >
                    {plan.rank > currentRank ? "Upgrade" : "Switch"} to {plan.name}
                  </Button>
                )}
              </CardFooter>
            </Card>
          );
        })}
      </div>

      <Card data-testid="pro-preview">
        <CardHeader>
          <div className="flex items-center gap-2">
            {proPreview.isSuccess ? (
              <Sparkles className="h-5 w-5 text-primary" />
            ) : (
              <Lock className="h-5 w-5 text-muted-foreground" />
            )}
            <CardTitle>Pro feature preview</CardTitle>
          </div>
          <CardDescription>
            AI media generation is available on the Pro and Team plans.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {proPreview.isPending ? (
            <p className="text-sm text-muted-foreground">Checking your plan…</p>
          ) : proPreview.isSuccess ? (
            <p className="flex items-center gap-2 text-sm" data-testid="pro-preview-unlocked">
              <Check className="h-4 w-4 shrink-0 text-primary" />
              {proPreview.data.message}
            </p>
          ) : (
            <p
              className="flex items-center gap-2 text-sm text-muted-foreground"
              data-testid="pro-preview-locked"
            >
              <Lock className="h-4 w-4 shrink-0" />
              Locked — upgrade to Pro or Team to unlock AI media generation.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
