import java.util.*;

public class Problem02_Rand10UsingRand7 {
    private Random rand = new Random();

    private int rand7() { return rand.nextInt(7) + 1; }

    public int rand10() {
        while (true) {
            int num = (rand7() - 1) * 7 + rand7(); // uniform in [1,49]
            if (num <= 40) return (num - 1) % 10 + 1;
        }
    }

    public static void main(String[] args) {
        Problem02_Rand10UsingRand7 sol = new Problem02_Rand10UsingRand7();
        int[] freq = new int[11];
        for (int i = 0; i < 10000; i++) freq[sol.rand10()]++;
        System.out.println(Arrays.toString(Arrays.copyOfRange(freq, 1, 11)));
    }
}
