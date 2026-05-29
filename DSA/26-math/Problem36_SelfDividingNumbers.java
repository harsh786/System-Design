/**
 * Problem 36: Self Dividing Numbers
 * A number is self-dividing if divisible by each of its digits (no zeros).
 *
 * Approach: Check each digit divides the number.
 * Time Complexity: O(n * d) where d is number of digits
 * Space Complexity: O(1) excluding output
 *
 * Production Analogy: Like input validation rules where each component
 * must satisfy a property relative to the whole.
 */
import java.util.ArrayList;
import java.util.List;

public class Problem36_SelfDividingNumbers {

    public static List<Integer> selfDividingNumbers(int left, int right) {
        List<Integer> result = new ArrayList<>();
        for (int num = left; num <= right; num++) {
            if (isSelfDividing(num)) result.add(num);
        }
        return result;
    }

    private static boolean isSelfDividing(int num) {
        int temp = num;
        while (temp > 0) {
            int d = temp % 10;
            if (d == 0 || num % d != 0) return false;
            temp /= 10;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(selfDividingNumbers(1, 22));
        // [1,2,3,4,5,6,7,8,9,11,12,15,22]
        System.out.println(selfDividingNumbers(47, 85));
    }
}
