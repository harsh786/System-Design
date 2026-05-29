public class Problem44_PriorityQueueMaxHeap {
    int[] heap; int size = 0;
    Problem44_PriorityQueueMaxHeap(int cap) { heap = new int[cap]; }
    void insert(int val) { heap[size] = val; siftUp(size++); }
    int extractMax() { int max = heap[0]; heap[0] = heap[--size]; siftDown(0); return max; }
    int peek() { return heap[0]; }
    void siftUp(int i) { while (i > 0 && heap[i] > heap[(i-1)/2]) { swap(i, (i-1)/2); i = (i-1)/2; } }
    void siftDown(int i) {
        while (2*i+1 < size) {
            int j = 2*i+1;
            if (j+1 < size && heap[j+1] > heap[j]) j++;
            if (heap[i] >= heap[j]) break;
            swap(i, j); i = j;
        }
    }
    void swap(int a, int b) { int t = heap[a]; heap[a] = heap[b]; heap[b] = t; }
    public static void main(String[] args) {
        Problem44_PriorityQueueMaxHeap pq = new Problem44_PriorityQueueMaxHeap(10);
        pq.insert(5); pq.insert(3); pq.insert(8); pq.insert(1);
        System.out.println(pq.extractMax()); // 8
        System.out.println(pq.extractMax()); // 5
    }
}
