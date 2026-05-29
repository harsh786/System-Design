import java.util.*;

public class Problem11_ReservoirSampling {
    // 382. Linked List Random Node / Reservoir Sampling for stream.
    // Pick one element uniformly at random from a stream.
    
    Random rand = new Random();
    int count = 0;
    int result = 0;
    
    public void feed(int val) {
        count++;
        if (rand.nextInt(count) == 0) result = val;
    }
    
    public int getSample() { return result; }
    
    // Reservoir sample of size k
    public static int[] reservoirSampleK(int[] stream, int k) {
        int[] reservoir = new int[k];
        Random r = new Random();
        for (int i = 0; i < stream.length; i++) {
            if (i < k) reservoir[i] = stream[i];
            else { int j = r.nextInt(i + 1); if (j < k) reservoir[j] = stream[i]; }
        }
        return reservoir;
    }
    
    public static void main(String[] args) {
        Problem11_ReservoirSampling sol = new Problem11_ReservoirSampling();
        for (int i = 1; i <= 10; i++) sol.feed(i);
        System.out.println("Sample: " + sol.getSample());
        System.out.println("Reservoir k=3: " + Arrays.toString(reservoirSampleK(new int[]{1,2,3,4,5,6,7,8,9,10}, 3)));
    }
}
