import java.util.*;

public class Problem10_ImplementRand10UsingRand7 {
    // Rejection sampling: rand7 * 7 + rand7 gives uniform 1-49
    static Random rand = new Random();

    static int rand7() { return rand.nextInt(7) + 1; }

    static int rand10() {
        while (true) {
            int num = (rand7() - 1) * 7 + rand7(); // 1..49
            if (num <= 40) return num % 10 + 1;
        }
    }

    public static void main(String[] args) {
        int[] freq = new int[11];
        for (int i = 0; i < 100000; i++) freq[rand10()]++;
        for (int i = 1; i <= 10; i++) System.out.println(i + ": " + freq[i]);
    }
}
