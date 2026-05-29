import java.util.*;

public class Problem13_ShuffleArray {
    private int[] original;
    private Random rand = new Random();

    public Problem13_ShuffleArray(int[] nums) { original = nums.clone(); }

    public int[] shuffle() {
        int[] arr = original.clone();
        for (int i = arr.length - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1);
            int t = arr[i]; arr[i] = arr[j]; arr[j] = t;
        }
        return arr;
    }

    public int[] reset() { return original.clone(); }

    public static void main(String[] args) {
        Problem13_ShuffleArray sol = new Problem13_ShuffleArray(new int[]{1,2,3,4,5});
        System.out.println(Arrays.toString(sol.shuffle()));
        System.out.println(Arrays.toString(sol.shuffle()));
        System.out.println(Arrays.toString(sol.reset()));
    }
}
