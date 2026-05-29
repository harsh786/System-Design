import java.util.*;

public class Problem04_TopKFrequentElements {
    /*
     * Top K Frequent Elements using Quickselect on frequency array
     * Time: O(n) average
     */
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        int[] unique = new int[freq.size()];
        int idx = 0;
        for (int key : freq.keySet()) unique[idx++] = key;
        int n = unique.length;
        quickselect(unique, freq, 0, n - 1, n - k);
        return Arrays.copyOfRange(unique, n - k, n);
    }

    private void quickselect(int[] arr, Map<Integer, Integer> freq, int lo, int hi, int k) {
        if (lo >= hi) return;
        int pi = partition(arr, freq, lo, hi);
        if (pi == k) return;
        else if (pi < k) quickselect(arr, freq, pi + 1, hi, k);
        else quickselect(arr, freq, lo, pi - 1, k);
    }

    private int partition(int[] arr, Map<Integer, Integer> freq, int lo, int hi) {
        int pivot = freq.get(arr[hi]);
        int s = lo;
        for (int i = lo; i < hi; i++) {
            if (freq.get(arr[i]) < pivot) { swap(arr, s, i); s++; }
        }
        swap(arr, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem04_TopKFrequentElements sol = new Problem04_TopKFrequentElements();
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{1,1,1,2,2,3}, 2)));
    }
}
