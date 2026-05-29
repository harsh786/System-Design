import java.util.*;

public class Problem07_ReservoirSampling {
    // Select k items from stream of unknown size uniformly
    public static int[] reservoirSample(int[] stream, int k) {
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
        int[] stream = {1,2,3,4,5,6,7,8,9,10};
        System.out.println(Arrays.toString(reservoirSample(stream, 3)));
        System.out.println(Arrays.toString(reservoirSample(stream, 3)));
    }
}
