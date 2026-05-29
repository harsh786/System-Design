import java.util.*;

public class Problem46_SortByFrequencyThenValue {
    public static int[] sortByFreqThenValue(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        Integer[] arr = new Integer[nums.length];
        for (int i = 0; i < nums.length; i++) arr[i] = nums[i];
        Arrays.sort(arr, (a, b) -> freq.get(a).equals(freq.get(b)) ? a - b : freq.get(b) - freq.get(a));
        for (int i = 0; i < nums.length; i++) nums[i] = arr[i];
        return nums;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortByFreqThenValue(new int[]{2,3,1,3,2,4,6,7,9,2,19})));
    }
}
