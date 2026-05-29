import java.util.*;

public class Problem18_ShuffleAnArray {
    int[] original;
    Random rand = new Random();
    
    Problem18_ShuffleAnArray(int[] nums) { original = nums.clone(); }
    
    int[] reset() { return original.clone(); }
    
    int[] shuffle() {
        int[] arr = original.clone();
        for (int i = arr.length - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1);
            int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
        }
        return arr;
    }
    
    public static void main(String[] args) {
        Problem18_ShuffleAnArray s = new Problem18_ShuffleAnArray(new int[]{1,2,3,4,5});
        System.out.println(Arrays.toString(s.shuffle()));
        System.out.println(Arrays.toString(s.reset()));
    }
}
