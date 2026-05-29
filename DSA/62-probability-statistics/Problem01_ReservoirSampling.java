import java.util.*;

public class Problem01_ReservoirSampling {
    private Random rand = new Random();

    public int sample(int[] stream) {
        int result = 0;
        for (int i = 0; i < stream.length; i++) {
            if (rand.nextInt(i + 1) == 0) result = stream[i];
        }
        return result;
    }

    public static void main(String[] args) {
        Problem01_ReservoirSampling sol = new Problem01_ReservoirSampling();
        int[] freq = new int[5];
        int[] stream = {0, 1, 2, 3, 4};
        for (int i = 0; i < 10000; i++) freq[sol.sample(stream)]++;
        System.out.println(Arrays.toString(freq));
    }
}
