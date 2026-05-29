import java.util.*;

public class Problem25_ReservoirSamplingK {
    public int[] sample(int[] stream, int k) {
        Random rand = new Random();
        int[] reservoir = new int[k];
        for (int i = 0; i < k; i++) reservoir[i] = stream[i];
        for (int i = k; i < stream.length; i++) {
            int j = rand.nextInt(i + 1);
            if (j < k) reservoir[j] = stream[i];
        }
        return reservoir;
    }

    public static void main(String[] args) {
        Problem25_ReservoirSamplingK sol = new Problem25_ReservoirSamplingK();
        int[] stream = new int[100];
        for (int i = 0; i < 100; i++) stream[i] = i;
        System.out.println(Arrays.toString(sol.sample(stream, 10)));
    }
}
