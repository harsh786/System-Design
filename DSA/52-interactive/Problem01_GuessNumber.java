import java.util.*;

public class Problem01_GuessNumber {
    // Guess Number Higher or Lower - Binary search with oracle feedback
    static int secret;
    
    static int guess(int num) {
        if (num == secret) return 0;
        return num > secret ? -1 : 1;
    }
    
    static int guessNumber(int n) {
        int lo = 1, hi = n;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int res = guess(mid);
            if (res == 0) return mid;
            else if (res == -1) hi = mid - 1;
            else lo = mid + 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        secret = 6;
        System.out.println("Secret=6, Guessed: " + guessNumber(10));
        secret = 1;
        System.out.println("Secret=1, Guessed: " + guessNumber(1));
    }
}
