import java.util.*;

public class Problem14_MergeSortOnIndexes {
    // Sort indices by values while tracking original positions
    static int[] sortIndexes(int[] nums) {
        int n = nums.length;
        Integer[] indices = new Integer[n];
        for (int i = 0; i < n; i++) indices[i] = i;
        Arrays.sort(indices, (a, b) -> nums[a] - nums[b]);
        int[] rank = new int[n];
        for (int i = 0; i < n; i++) rank[indices[i]] = i;
        return rank;
    }
    
    public static void main(String[] args) {
        int[] nums = {40, 10, 30, 20};
        System.out.println(Arrays.toString(sortIndexes(nums))); // [3, 0, 2, 1]
    }
}
