import java.util.*;

public class Problem30_SecondLargestElement {
    public int secondLargest(int[] arr) {
        int first = Integer.MIN_VALUE, second = Integer.MIN_VALUE;
        for (int x : arr) {
            if (x > first) { second = first; first = x; }
            else if (x > second && x != first) second = x;
        }
        return second;
    }

    public static void main(String[] args) {
        Problem30_SecondLargestElement sol = new Problem30_SecondLargestElement();
        System.out.println(sol.secondLargest(new int[]{12, 35, 1, 10, 34, 1})); // 34
    }
}
