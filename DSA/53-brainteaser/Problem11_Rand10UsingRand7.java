import java.util.*;

public class Problem11_Rand10UsingRand7 {
    static Random rng = new Random(42);
    static int rand7() { return rng.nextInt(7) + 1; }
    
    static int rand10() {
        while (true) {
            int num = (rand7() - 1) * 7 + rand7(); // 1..49 uniform
            if (num <= 40) return (num - 1) % 10 + 1;
        }
    }
    
    public static void main(String[] args) {
        int[] count = new int[11];
        for (int i = 0; i < 100000; i++) count[rand10()]++;
        for (int i = 1; i <= 10; i++) System.out.println(i + ": " + count[i]);
    }
}
