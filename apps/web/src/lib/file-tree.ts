import type { FileMetadata } from "@ai-saas-starter-kit/shared";

export interface TreeFolder {
  type: "folder";
  name: string;
  path: string;
  children: TreeNode[];
}

export interface TreeFile {
  type: "file";
  name: string;
  data: FileMetadata;
}

export type TreeNode = TreeFolder | TreeFile;

/**
 * Build a tree structure from a flat list of S3 keys.
 * e.g. ["uploads/a.jpg", "uploads/photos/b.png", "docs/c.pdf"]
 * becomes a nested folder/file hierarchy.
 */
export function buildFileTree(files: FileMetadata[]): TreeNode[] {
  const root: TreeFolder = {
    type: "folder",
    name: "",
    path: "",
    children: [],
  };

  for (const file of files) {
    const parts = file.key.split("/");
    let current = root;

    // Walk/create folders for all parts except the last (filename)
    for (let i = 0; i < parts.length - 1; i++) {
      const folderName = parts[i];
      const folderPath = parts.slice(0, i + 1).join("/") + "/";
      let folder = current.children.find(
        (c): c is TreeFolder => c.type === "folder" && c.name === folderName
      );
      if (!folder) {
        folder = {
          type: "folder",
          name: folderName,
          path: folderPath,
          children: [],
        };
        current.children.push(folder);
      }
      current = folder;
    }

    // Add the file as a leaf
    current.children.push({
      type: "file",
      name: file.filename,
      data: file,
    });
  }

  // Sort: folders first (alphabetical), then files (most recent first)
  sortTree(root.children);

  return root.children;
}

function sortTree(nodes: TreeNode[]) {
  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    if (a.type === "folder" && b.type === "folder") {
      return a.name.localeCompare(b.name);
    }
    // Files: most recent first
    if (a.type === "file" && b.type === "file") {
      return (
        new Date(b.data.uploaded_at).getTime() -
        new Date(a.data.uploaded_at).getTime()
      );
    }
    return 0;
  });

  for (const node of nodes) {
    if (node.type === "folder") {
      sortTree(node.children);
    }
  }
}
