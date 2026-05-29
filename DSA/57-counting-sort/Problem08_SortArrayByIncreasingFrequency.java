import java.util.*;

public class Problem08_SortArrayByIncreasingFrequency {
    public static int[] frequencySort(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        Integer[] arr = new Integer[nums.length];
        for (int i = 0; i < nums.length; i++) arr[i] = nums[i];
        Arrays.sort(arr, (a, b) -> freq.get(a) != freq.get(b) ? freq.get(a) - freq.get(b) : b - a);
        for (int i = 0; i < nums.length; i++) nums[i] = arr[i];
        return nums;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(frequencySort(new int[]{1,1,2,2,2,3})));
        // [3,1,1,2,2,2]
    }
}
