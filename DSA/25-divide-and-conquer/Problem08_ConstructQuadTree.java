/**
 * Problem 8: Construct Quad Tree (LeetCode 427)
 * 
 * D&C Approach:
 * - DIVIDE: Split grid into 4 quadrants (top-left, top-right, bottom-left, bottom-right)
 * - CONQUER: Recursively build quad tree for each quadrant
 * - COMBINE: If all 4 children are leaves with same value, merge into single leaf
 * 
 * Time: O(n^2 * log n), Space: O(n^2)
 * 
 * Production Analogy:
 * - Spatial indexing (quad trees for 2D space partitioning in GIS)
 * - Image compression (similar regions compressed to single node)
 * - Collision detection in game engines
 */
public class Problem08_ConstructQuadTree {

    static class Node {
        boolean val, isLeaf;
        Node topLeft, topRight, bottomLeft, bottomRight;
        Node(boolean val, boolean isLeaf) { this.val = val; this.isLeaf = isLeaf; }
    }

    public static Node construct(int[][] grid) {
        return build(grid, 0, 0, grid.length);
    }

    private static Node build(int[][] grid, int row, int col, int size) {
        if (size == 1) {
            return new Node(grid[row][col] == 1, true);
        }
        
        int half = size / 2;
        Node topLeft = build(grid, row, col, half);
        Node topRight = build(grid, row, col + half, half);
        Node bottomLeft = build(grid, row + half, col, half);
        Node bottomRight = build(grid, row + half, col + half, half);
        
        // Merge if all children are leaves with same value
        if (topLeft.isLeaf && topRight.isLeaf && bottomLeft.isLeaf && bottomRight.isLeaf
            && topLeft.val == topRight.val && topRight.val == bottomLeft.val && bottomLeft.val == bottomRight.val) {
            return new Node(topLeft.val, true);
        }
        
        Node node = new Node(true, false);
        node.topLeft = topLeft; node.topRight = topRight;
        node.bottomLeft = bottomLeft; node.bottomRight = bottomRight;
        return node;
    }

    private static void printTree(Node node, String prefix) {
        if (node == null) return;
        System.out.println(prefix + "Leaf=" + node.isLeaf + " Val=" + node.val);
        if (!node.isLeaf) {
            printTree(node.topLeft, prefix + "  TL:");
            printTree(node.topRight, prefix + "  TR:");
            printTree(node.bottomLeft, prefix + "  BL:");
            printTree(node.bottomRight, prefix + "  BR:");
        }
    }

    public static void main(String[] args) {
        int[][] grid1 = {{0,1},{1,0}};
        printTree(construct(grid1), "");
        System.out.println("---");
        
        int[][] grid2 = {{1,1},{1,1}};
        printTree(construct(grid2), "");
        System.out.println("---");
        
        int[][] grid3 = {
            {1,1,0,0},
            {1,1,0,0},
            {0,0,1,1},
            {0,0,1,1}
        };
        printTree(construct(grid3), "");
    }
}
