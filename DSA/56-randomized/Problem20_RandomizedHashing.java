import java.util.*;

public class Problem20_RandomizedHashing {
    // Universal hashing: h(x) = ((a*x + b) mod p) mod m
    static int universalHash(int key, int a, int b, int p, int m) {
        return (int)(((long)a * key + b) % p % m);
    }

    public static void main(String[] args) {
        Random rand = new Random();
        int p = 1000000007, m = 100;
        int a = rand.nextInt(p - 1) + 1;
        int b = rand.nextInt(p);
        int[] keys = {10, 20, 30, 40, 50, 60};
        System.out.println("Hash function: h(x) = ((" + a + "*x + " + b + ") mod " + p + ") mod " + m);
        for (int k : keys) System.out.println("h(" + k + ") = " + universalHash(k, a, b, p, m));
    }
}
