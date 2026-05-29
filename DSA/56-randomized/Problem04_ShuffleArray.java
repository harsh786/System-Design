import java.util.*;

public class Problem04_ShuffleArray {
    // Fisher-Yates shuffle algorithm
    int[] original;
    int[] array;
    Random rand;

    public Problem04_ShuffleArray(int[] nums) {
        original = nums.clone();
        array = nums.clone();
        rand = new Random();
    }

    public int[] reset() {
        array = original.clone();
        return array;
    }

    public int[] shuffle() {
        for (int i = array.length - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1);
            int tmp = array[i]; array[i] = array[j]; array[j] = tmp;
        }
        return array;
    }

    public static void main(String[] args) {
        Problem04_ShuffleArray sol = new Problem04_ShuffleArray(new int[]{1, 2, 3});
        System.out.println(Arrays.toString(sol.shuffle()));
        System.out.println(Arrays.toString(sol.reset()));
        System.out.println(Arrays.toString(sol.shuffle()));
    }
}
