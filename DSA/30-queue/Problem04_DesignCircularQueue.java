public class Problem04_DesignCircularQueue {
    int[] data; int head = 0, count = 0, cap;
    public Problem04_DesignCircularQueue(int k) { data = new int[k]; cap = k; }
    public boolean enQueue(int value) { if (isFull()) return false; data[(head + count) % cap] = value; count++; return true; }
    public boolean deQueue() { if (isEmpty()) return false; head = (head + 1) % cap; count--; return true; }
    public int Front() { return isEmpty() ? -1 : data[head]; }
    public int Rear() { return isEmpty() ? -1 : data[(head + count - 1) % cap]; }
    public boolean isEmpty() { return count == 0; }
    public boolean isFull() { return count == cap; }
    public static void main(String[] args) {
        Problem04_DesignCircularQueue q = new Problem04_DesignCircularQueue(3);
        System.out.println(q.enQueue(1)); System.out.println(q.enQueue(2)); System.out.println(q.enQueue(3));
        System.out.println(q.enQueue(4)); // false
        System.out.println(q.Rear()); // 3
        System.out.println(q.isFull()); // true
    }
}
