import java.util.*;

public class Problem27_RandomizedSamplingFromStream {
    // Online reservoir sampling from infinite stream
    int[] reservoir;
    int count;
    int k;
    Random rand = new Random();

    public Problem27_RandomizedSamplingFromStream(int k) { this.k = k; reservoir = new int[k]; count = 0; }

    public void consume(int item) {
        if (count < k) { reservoir[count] = item; }
        else { int j = rand.nextInt(count + 1); if (j < k) reservoir[j] = item; }
        count++;
    }

    public int[] getSample() { return Arrays.copyOf(reservoir, Math.min(count, k)); }

    public static void main(String[] args) {
        Problem27_RandomizedSamplingFromStream s = new Problem27_RandomizedSamplingFromStream(3);
        for (int i = 1; i <= 100; i++) s.consume(i);
        System.out.println(Arrays.toString(s.getSample()));
    }
}
