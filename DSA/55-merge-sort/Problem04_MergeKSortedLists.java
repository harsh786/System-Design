import java.util.*;

public class Problem04_MergeKSortedLists {
    static class ListNode{int val;ListNode next;ListNode(int v){val=v;}}
    
    static ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq=new PriorityQueue<>((a,b)->a.val-b.val);
        for(ListNode l:lists)if(l!=null)pq.offer(l);
        ListNode d=new ListNode(0),c=d;
        while(!pq.isEmpty()){ListNode n=pq.poll();c.next=n;c=c.next;if(n.next!=null)pq.offer(n.next);}
        return d.next;
    }
    
    public static void main(String[] args) {
        ListNode a=new ListNode(1);a.next=new ListNode(4);
        ListNode b=new ListNode(2);b.next=new ListNode(3);
        ListNode c=new ListNode(0);c.next=new ListNode(5);
        ListNode r=mergeKLists(new ListNode[]{a,b,c});
        while(r!=null){System.out.print(r.val+" ");r=r.next;}System.out.println();
    }
}
