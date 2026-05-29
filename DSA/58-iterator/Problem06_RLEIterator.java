import java.util.*;

public class Problem06_RLEIterator {
    int[] encoding;
    int idx;

    public Problem06_RLEIterator(int[] encoding) { this.encoding = encoding; idx = 0; }

    public int next(int n) {
        while (idx < encoding.length) {
            if (encoding[idx] >= n) { encoding[idx] -= n; return encoding[idx + 1]; }
            n -= encoding[idx];
            idx += 2;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem06_RLEIterator it = new Problem06_RLEIterator(new int[]{3,8,0,9,2,5});
        System.out.println(it.next(2)); // 8
        System.out.println(it.next(1)); // 8
        System.out.println(it.next(1)); // 5
        System.out.println(it.next(2)); // -1
    }
}
