import java.util.*;

public class Problem29_CountingSortForHistogram {
    public static int[] buildHistogram(int[] data, int bucketSize) {
        int max = Arrays.stream(data).max().orElse(0);
        int numBuckets = max / bucketSize + 1;
        int[] histogram = new int[numBuckets];
        for (int d : data) histogram[d / bucketSize]++;
        return histogram;
    }

    public static void main(String[] args) {
        int[] data = {5, 12, 3, 18, 25, 8, 15, 22, 1, 30};
        int[] hist = buildHistogram(data, 10);
        for (int i = 0; i < hist.length; i++)
            System.out.println("[" + i*10 + "-" + ((i+1)*10-1) + "]: " + hist[i]);
    }
}
