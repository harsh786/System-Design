import java.util.*;

public class Problem38_InteractiveTreeHeight {
    static int[] left = {1, 3, 5, -1, -1, -1, -1};
    static int[] right = {2, 4, 6, -1, -1, -1, -1};
    
    static int getLeft(int node) { return node < left.length ? left[node] : -1; }
    static int getRight(int node) { return node < right.length ? right[node] : -1; }
    
    static int height(int root) {
        if (root == -1) return 0;
        return 1 + Math.max(height(getLeft(root)), height(getRight(root)));
    }
    
    public static void main(String[] args) {
        System.out.println("Tree height: " + height(0)); // 3
    }
}
