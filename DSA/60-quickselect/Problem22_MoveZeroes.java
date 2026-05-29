import java.util.*;

public class Problem22_MoveZeroes {
    public void moveZeroes(int[] nums) {
        int insertPos = 0;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] != 0) nums[insertPos++] = nums[i];
        }
        while (insertPos < nums.length) nums[insertPos++] = 0;
    }

    public static void main(String[] args) {
        Problem22_MoveZeroes sol = new Problem22_MoveZeroes();
        int[] arr = {0, 1, 0, 3, 12};
        sol.moveZeroes(arr);
        System.out.println(Arrays.toString(arr));
    }
}
