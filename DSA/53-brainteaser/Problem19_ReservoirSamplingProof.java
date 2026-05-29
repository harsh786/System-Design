import java.util.*;

public class Problem19_ReservoirSamplingProof {
    // Reservoir Sampling: each element has equal 1/n probability
    static int[] reservoirSample(int[] stream, int k) {
        int[] reservoir = new int[k];
        Random rand = new Random();
        for (int i = 0; i < k; i++) reservoir[i] = stream[i];
        for (int i = k; i < stream.length; i++) {
            int j = rand.nextInt(i + 1);
            if (j < k) reservoir[j] = stream[i];
        }
        return reservoir;
    }
    
    public static void main(String[] args) {
        int[] stream = {0,1,2,3,4,5,6,7,8,9};
        int[] freq = new int[10];
        for (int t = 0; t < 100000; t++) {
            int[] sample = reservoirSample(stream, 3);
            for (int s : sample) freq[s]++;
        }
        System.out.println("Each ~30000: " + Arrays.toString(freq));
    }
}
