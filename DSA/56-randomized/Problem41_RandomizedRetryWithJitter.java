import java.util.*;

public class Problem41_RandomizedRetryWithJitter {
    static Random rand = new Random();

    // Decorrelated jitter (AWS recommended)
    public static long decorrelatedJitter(int attempt, long baseMs, long maxMs, long[] prevSleep) {
        long sleep;
        if (attempt == 0) sleep = baseMs;
        else sleep = Math.min(maxMs, (long)(rand.nextDouble() * (prevSleep[0] * 3 - baseMs) + baseMs));
        prevSleep[0] = sleep;
        return sleep;
    }

    public static void main(String[] args) {
        long[] prev = {100};
        for (int i = 0; i < 8; i++)
            System.out.println("Attempt " + i + ": sleep " + decorrelatedJitter(i, 100, 10000, prev) + "ms");
    }
}
