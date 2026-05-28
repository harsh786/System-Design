import java.util.*;

/**
 * Problem 39: Build an Array With Stack Operations (LeetCode 1441)
 * 
 * Given target array and n, use Push/Pop operations on stream 1..n to build target.
 * 
 * Approach: Iterate 1 to n. If number matches next target element, Push.
 * Otherwise Push then Pop (skip it).
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like filtering a data stream using accept/reject operations,
 * recording the operation log for replay/audit purposes.
 */
public class Problem39_BuildArrayWithStackOperations {

    public static List<String> buildArray(int[] target, int n) {
        List<String> ops = new ArrayList<>();
        int j = 0;
        for (int i = 1; i <= n && j < target.length; i++) {
            ops.add("Push");
            if (target[j] == i) {
                j++;
            } else {
                ops.add("Pop");
            }
        }
        return ops;
    }

    public static void main(String[] args) {
        System.out.println(buildArray(new int[]{1,3}, 3)); // [Push, Push, Pop, Push]
        System.out.println(buildArray(new int[]{1,2,3}, 3)); // [Push, Push, Push]
        System.out.println(buildArray(new int[]{1,2}, 4)); // [Push, Push]
    }
}
