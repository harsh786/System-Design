import java.util.*;

public class Problem20_TwentyQuestionsStrategy {
    // Binary search strategy for 20 questions - find number in range
    static int secret = 742;
    
    static boolean isLessOrEqual(int guess) { return secret <= guess; }
    
    static int play(int maxVal) {
        int lo = 1, hi = maxVal, questions = 0;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            questions++;
            if (isLessOrEqual(mid)) hi = mid;
            else lo = mid + 1;
        }
        System.out.println("Questions asked: " + questions);
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("Found: " + play(1000000)); // 742, ~20 questions
    }
}
