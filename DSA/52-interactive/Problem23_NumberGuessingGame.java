import java.util.*;

public class Problem23_NumberGuessingGame {
    static int secret = 50;
    static int maxGuesses = 10;
    
    static int compare(int guess) { return Integer.compare(secret, guess); }
    
    static int play(int lo, int hi) {
        int guesses = 0;
        while (lo <= hi && guesses < maxGuesses) {
            int mid = lo + (hi - lo) / 2;
            guesses++;
            int cmp = compare(mid);
            if (cmp == 0) { System.out.println("Found in " + guesses + " guesses"); return mid; }
            else if (cmp > 0) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Result: " + play(1, 100));
    }
}
