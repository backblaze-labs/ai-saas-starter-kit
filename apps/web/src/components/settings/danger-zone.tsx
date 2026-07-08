"use client";

import { AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export function DangerZone() {
  const onConfirm = () => {
    toast.success("Bucket cleared", {
      description: "This is a demo — no files were actually deleted.",
    });
  };

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
              Delete every file in the B2 bucket.
            </p>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm">
                Empty bucket
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Empty the bucket?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently remove all files. This is a demo — no
                  real delete will run.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={onConfirm}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Yes, empty it
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  );
}
