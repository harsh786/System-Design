import java.util.*;

public class Problem45_HistogramEqualizationSort {
    // Redistribute values to uniform distribution using counting sort
    public static int[] equalize(int[] data, int levels) {
        int[] hist = new int[levels];
        for (int d : data) hist[d]++;
        // CDF
        int[] cdf = new int[levels];
        cdf[0] = hist[0];
        for (int i = 1; i < levels; i++) cdf[i] = cdf[i-1] + hist[i];
        int total = data.length;
        int[] result = new int[data.length];
        for (int i = 0; i < data.length; i++)
            result[i] = (int)((double)(cdf[data[i]] - 1) / (total - 1) * (levels - 1));
        return result;
    }

    public static void main(String[] args) {
        int[] data = {0,0,1,1,2,2,3,3,4,4,4,4,5,5,5,5};
        System.out.println(Arrays.toString(equalize(data, 6)));
    }
}
