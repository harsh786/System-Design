import java.util.*;

public class Problem42_DLLMRUQueue {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head=new Node(0),tail=new Node(0);int size;
    
    Problem42_DLLMRUQueue(int n){head.next=tail;tail.prev=head;for(int i=1;i<=n;i++){Node nd=new Node(i);nd.prev=tail.prev;nd.next=tail;tail.prev.next=nd;tail.prev=nd;size++;}}
    
    int fetch(int k){// fetch k-th element, move to end
        Node cur=head.next;for(int i=1;i<k;i++)cur=cur.next;
        cur.prev.next=cur.next;cur.next.prev=cur.prev;
        cur.prev=tail.prev;cur.next=tail;tail.prev.next=cur;tail.prev=cur;
        return cur.val;
    }
    
    public static void main(String[] args) {
        Problem42_DLLMRUQueue q=new Problem42_DLLMRUQueue(5);
        System.out.println(q.fetch(3)); // 3
        System.out.println(q.fetch(3)); // 4 (since 3 moved to end)
    }
}
