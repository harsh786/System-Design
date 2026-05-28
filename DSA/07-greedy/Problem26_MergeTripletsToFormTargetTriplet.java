/**
 * Problem 26: Merge Triplets to Form Target Triplet (LeetCode 1899)
 *
 * Greedy Choice: A triplet is usable if none of its values exceed the target's corresponding value.
 * Among usable triplets, check if we can achieve each target value.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Selecting compatible service versions that together meet feature requirements.
 */
public class Problem26_MergeTripletsToFormTargetTriplet {
    
    public static boolean mergeTriplets(int[][] triplets, int[] target) {
        boolean[] found = new boolean[3];
        for (int[] t : triplets) {
            if (t[0] <= target[0] && t[1] <= target[1] && t[2] <= target[2]) {
                if (t[0] == target[0]) found[0] = true;
                if (t[1] == target[1]) found[1] = true;
                if (t[2] == target[2]) found[2] = true;
            }
        }
        return found[0] && found[1] && found[2];
    }
    
    public static void main(String[] args) {
        System.out.println(mergeTriplets(new int[][]{{2,5,3},{1,8,4},{1,7,5}}, new int[]{2,7,5})); // true
        System.out.println(mergeTriplets(new int[][]{{3,4,5},{4,5,6}}, new int[]{3,2,5}));          // false
    }
}
