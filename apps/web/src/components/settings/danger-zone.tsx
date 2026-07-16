"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function DangerZone() {
  return (
    <Card className="border-destructive/40">
      <CardHeader className="border-b border-destructive/30 py-4 px-5">
        <CardTitle className="card-title text-destructive">Danger Zone</CardTitle>
      </CardHeader>
      <CardContent className="p-5 space-y-4">
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Irreversible actions</AlertTitle>
          <AlertDescription>
            These actions permanently delete data. There is no undo.
          </AlertDescription>
        </Alert>
        <div className="flex items-center justify-between rounded-md border border-destructive/30 p-3">
          <div>
            <p className="text-sm font-medium">Empty this bucket</p>
            <p className="text-xs text-muted-foreground">
              Delete every file in the B2 bucket. Not available in this starter.
            </p>
          </div>
          <Button variant="outline" size="sm" disabled>
            Empty bucket
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
