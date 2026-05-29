import java.util.*;

/**
 * Problem 50: Tournament Tree (Winner/Loser Tree)
 * 
 * D&C Approach:
 * - DIVIDE: Pair up elements in brackets (like a sports tournament)
 * - CONQUER: Compare pairs, winners advance to next round
 * - COMBINE: Final winner is the overall min/max
 * - To find 2nd best: among elements that lost to the winner (log n comparisons)
 * 
 * Time: Build O(n), Find min O(1), Update O(log n), 2nd min O(log n)
 * Space: O(n)
 * 
 * Production Analogy:
 * - K-way merge using loser trees (faster than priority queues for external sort)
 * - Tournament scheduling algorithms
 * - Selection algorithms (finding top-k with minimal comparisons)
 * - Replacement selection in external sort run generation
 */
public class Problem50_TournamentTree {

    private int[] tree;  // Internal nodes store winner indices
    private int[] data;  // Leaf data
    private int n;       // Number of players (leaves)

    public Problem50_TournamentTree(int[] input) {
        this.n = input.length;
        this.data = Arrays.copyOf(input, n);
        this.tree = new int[2 * n]; // tree[1] = root (overall winner index)
        buildTree();
    }

    private void buildTree() {
        // Leaves are at positions n to 2n-1
        for (int i = 0; i < n; i++) tree[n + i] = i;
        // Build internal nodes bottom-up
        for (int i = n - 1; i >= 1; i--) {
            int left = tree[2 * i], right = tree[2 * i + 1];
            tree[i] = (data[left] <= data[right]) ? left : right;
        }
    }

    public int getMin() {
        return data[tree[1]];
    }

    public int getMinIndex() {
        return tree[1];
    }

    // Replace winner with new value and replay
    public void replaceMin(int newVal) {
        int idx = tree[1];
        data[idx] = newVal;
        // Replay from leaf to root
        int pos = (n + idx) / 2;
        while (pos >= 1) {
            int left = tree[2 * pos], right = tree[2 * pos + 1];
            tree[pos] = (data[left] <= data[right]) ? left : right;
            pos /= 2;
        }
    }

    // Find second minimum in O(log n)
    public int getSecondMin() {
        int winnerIdx = tree[1];
        int secondMin = Integer.MAX_VALUE;
        // Check all opponents of the winner on its path
        int pos = n + winnerIdx;
        while (pos > 1) {
            int sibling = pos ^ 1; // Sibling in the tree
            if (sibling < 2 * n) {
                int sibIdx = (sibling >= n) ? sibling - n : tree[sibling];
                if (sibIdx < n) secondMin = Math.min(secondMin, data[sibIdx]);
            }
            pos /= 2;
        }
        return secondMin;
    }

    // K-way merge using tournament tree
    public static int[] kWayMerge(int[][] arrays) {
        int k = arrays.length;
        int total = 0;
        for (int[] a : arrays) total += a.length;
        
        int[] result = new int[total];
        int[] indices = new int[k]; // Current position in each array
        int[] current = new int[k]; // Current values
        
        for (int i = 0; i < k; i++) {
            current[i] = (arrays[i].length > 0) ? arrays[i][0] : Integer.MAX_VALUE;
        }
        
        Problem50_TournamentTree tt = new Problem50_TournamentTree(current);
        
        for (int i = 0; i < total; i++) {
            int minIdx = tt.getMinIndex();
            result[i] = tt.getMin();
            indices[minIdx]++;
            int newVal = (indices[minIdx] < arrays[minIdx].length) 
                         ? arrays[minIdx][indices[minIdx]] : Integer.MAX_VALUE;
            tt.replaceMin(newVal);
        }
        return result;
    }

    public static void main(String[] args) {
        // Basic tournament tree
        Problem50_TournamentTree tt = new Problem50_TournamentTree(new int[]{5, 3, 8, 1, 9, 2, 7, 4});
        System.out.println("Min: " + tt.getMin()); // 1
        System.out.println("2nd Min: " + tt.getSecondMin()); // 2
        
        tt.replaceMin(6);
        System.out.println("After replacing min with 6, new min: " + tt.getMin()); // 2
        
        // K-way merge using tournament tree
        int[][] arrays = {{1, 5, 9}, {2, 4, 8}, {3, 6, 7}};
        System.out.println("K-way merge: " + Arrays.toString(kWayMerge(arrays)));
        
        int[][] arrays2 = {{1, 3}, {2, 4}, {0, 5}};
        System.out.println("K-way merge: " + Arrays.toString(kWayMerge(arrays2)));
    }
}
