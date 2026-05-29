import java.util.*;

public class Problem14_RandomizedLoadBalancing {
    // Power of two choices: pick 2 random servers, choose less loaded
    static int[] serverLoad;
    static Random rand = new Random();

    static int pickServer(int n) {
        int a = rand.nextInt(n), b = rand.nextInt(n);
        return serverLoad[a] <= serverLoad[b] ? a : b;
    }

    public static void main(String[] args) {
        int n = 5;
        serverLoad = new int[n];
        for (int i = 0; i < 20; i++) {
            int server = pickServer(n);
            serverLoad[server]++;
        }
        System.out.println("Load distribution: " + Arrays.toString(serverLoad));
    }
}
