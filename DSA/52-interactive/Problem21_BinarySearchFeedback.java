import java.util.*;

public class Problem21_BinarySearchFeedback {
    static int target = 37;
    // Returns: "higher", "lower", "correct"
    static String feedback(int guess) {
        if (guess == target) return "correct";
        return guess < target ? "higher" : "lower";
    }
    
    static int solve(int lo, int hi) {
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            String fb = feedback(mid);
            if (fb.equals("correct")) return mid;
            else if (fb.equals("higher")) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Found: " + solve(1, 100));
    }
}
