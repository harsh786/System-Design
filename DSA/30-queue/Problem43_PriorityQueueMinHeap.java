import java.util.*;

public class Problem43_PriorityQueueMinHeap {
    int[] heap; int size = 0;
    Problem43_PriorityQueueMinHeap(int cap) { heap = new int[cap]; }
    void insert(int val) { heap[size] = val; siftUp(size++); }
    int extractMin() { int min = heap[0]; heap[0] = heap[--size]; siftDown(0); return min; }
    int peek() { return heap[0]; }
    boolean isEmpty() { return size == 0; }
    void siftUp(int i) { while (i > 0 && heap[i] < heap[(i-1)/2]) { swap(i, (i-1)/2); i = (i-1)/2; } }
    void siftDown(int i) {
        while (2*i+1 < size) {
            int j = 2*i+1;
            if (j+1 < size && heap[j+1] < heap[j]) j++;
            if (heap[i] <= heap[j]) break;
            swap(i, j); i = j;
        }
    }
    void swap(int a, int b) { int t = heap[a]; heap[a] = heap[b]; heap[b] = t; }
    public static void main(String[] args) {
        Problem43_PriorityQueueMinHeap pq = new Problem43_PriorityQueueMinHeap(10);
        pq.insert(5); pq.insert(3); pq.insert(8); pq.insert(1);
        System.out.println(pq.extractMin()); // 1
        System.out.println(pq.extractMin()); // 3
    }
}
