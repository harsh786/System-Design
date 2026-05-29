import java.util.*;

public class Problem49_DLLForPriorityQueueBuckets {
    // Bucket-based priority queue with DLL for each bucket
    static class Node{int id;Node prev,next;Node(int i){id=i;}}
    static class Bucket{Node head=new Node(-1),tail=new Node(-1);Bucket(){head.next=tail;tail.prev=head;}
        void add(Node n){n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;}
        Node removeFirst(){if(head.next==tail)return null;Node n=head.next;head.next=n.next;n.next.prev=head;return n;}
        boolean isEmpty(){return head.next==tail;}}
    
    Bucket[] buckets;int maxPri;int curMax=0;
    Problem49_DLLForPriorityQueueBuckets(int maxPriority){maxPri=maxPriority;buckets=new Bucket[maxPri+1];for(int i=0;i<=maxPri;i++)buckets[i]=new Bucket();}
    
    void insert(int id,int priority){buckets[priority].add(new Node(id));curMax=Math.max(curMax,priority);}
    int extractMax(){while(curMax>=0&&buckets[curMax].isEmpty())curMax--;if(curMax<0)return -1;return buckets[curMax].removeFirst().id;}
    
    public static void main(String[] args) {
        Problem49_DLLForPriorityQueueBuckets pq=new Problem49_DLLForPriorityQueueBuckets(10);
        pq.insert(1,3);pq.insert(2,7);pq.insert(3,5);pq.insert(4,7);
        System.out.println(pq.extractMax()); // 2
        System.out.println(pq.extractMax()); // 4
        System.out.println(pq.extractMax()); // 3
    }
}
