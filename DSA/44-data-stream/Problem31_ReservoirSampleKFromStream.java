import java.util.*;

public class Problem31_ReservoirSampleKFromStream {
    // Reservoir Sampling: Maintain k random samples from an infinite stream.
    
    int[] reservoir;
    int k, count;
    Random rand = new Random();
    
    public Problem31_ReservoirSampleKFromStream() { init(5); }
    
    public void init(int k) { this.k = k; reservoir = new int[k]; count = 0; }
    
    public void feed(int val) {
        if (count < k) { reservoir[count] = val; }
        else { int j = rand.nextInt(count + 1); if (j < k) reservoir[j] = val; }
        count++;
    }
    
    public int[] getSample() { return Arrays.copyOf(reservoir, Math.min(count, k)); }
    
    public static void main(String[] args) {
        Problem31_ReservoirSampleKFromStream sol = new Problem31_ReservoirSampleKFromStream();
        sol.init(3);
        for (int i = 1; i <= 100; i++) sol.feed(i);
        System.out.println("Reservoir sample: " + Arrays.toString(sol.getSample()));
    }
}
